"""Internal Pretix Order creation via the Django ORM.
Replaces devcon's services/pretix.ts REST API calls — we're inside Pretix
so we use the ORM directly.

Supports the same fields as the devcon implementation:
- variations (item.variations)
- addons (addon_to relationship)
- answers (QuestionAnswer per position, with option mapping for C/M types)
- voucher (optional per-item)
- attendee info (name, email, company, country)
- custom per-position price (e.g., voucher-discounted)
"""
import logging
from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django_scopes import scopes_disabled

log = logging.getLogger(__name__)


def _resolve_voucher(event, code: str):
    """Look up a Voucher by code. Returns None if not found."""
    if not code:
        return None
    try:
        from pretix.base.models import Voucher
        return Voucher.objects.get(event=event, code__iexact=code)
    except Exception:
        return None


def _build_answer_value(question, raw_answer):
    """Given a Question instance and the raw answer from the client, return
    a tuple (answer_string, option_pks, options_queryset) suitable for
    QuestionAnswer.answer + .options assignment."""
    if raw_answer is None:
        return None, [], None
    # Choice questions (C=single, M=multi) map to option IDs
    if question.type in ('C', 'M'):
        raw_ids = raw_answer if isinstance(raw_answer, list) else [raw_answer]
        option_pks = []
        for r in raw_ids:
            try:
                option_pks.append(int(str(r)))
            except (TypeError, ValueError):
                continue
        if not option_pks:
            return None, [], None
        opts = list(question.options.filter(pk__in=option_pks))
        if not opts:
            return None, [], None
        answer_str = ', '.join(str(o.answer) for o in opts)
        return answer_str, [o.pk for o in opts], opts
    # Non-choice: string / number / date / bool
    if isinstance(raw_answer, list):
        answer_str = ', '.join(str(x) for x in raw_answer if x not in (None, ''))
    else:
        answer_str = str(raw_answer)
    answer_str = answer_str.strip()
    return (answer_str or None), [], None


def _create_answers_for_position(position, answers_input, event, item_id):
    """Create QuestionAnswer rows for a position, filtered to questions that apply to item_id."""
    if not answers_input:
        return
    from pretix.base.models import Question, QuestionAnswer
    for a in answers_input:
        qid = a.get('questionId') or a.get('question')
        if not qid:
            continue
        try:
            question = Question.objects.filter(event=event, pk=int(qid)).first()
        except (TypeError, ValueError):
            continue
        if not question:
            continue
        # Skip if question doesn't apply to this item
        applies = list(question.items.values_list('pk', flat=True))
        if applies and item_id not in applies:
            continue
        answer_str, option_pks, opts = _build_answer_value(question, a.get('answer'))
        if not answer_str:
            continue
        qa = QuestionAnswer.objects.create(
            orderposition=position, question=question, answer=answer_str,
        )
        if opts:
            qa.options.set(opts)


def create_pretix_order(*, event, order_data: dict, total_usd: str):
    """Create a Pretix Order with the walletconnect payment provider.
    Returns the Order instance.

    order_data shape (from pending order):
    {
      email: str,
      tickets: [{itemId, variationId?, quantity, price?}],  # price optional (voucher-discounted)
      addons: [{itemId, variationId?, quantity, price?}],   # linked to first ticket
      answers: [{questionId, answer}],
      attendee: { name: {given_name, family_name}, email?, company?, country? },
      voucher: str | None,
    }
    """
    from pretix.base.models import Order, OrderPosition, Item, ItemVariation
    with scopes_disabled():
        sc = event.organizer.sales_channels.get(identifier='web')
        order = Order.objects.create(
            event=event,
            email=order_data['email'],
            status=Order.STATUS_PENDING,
            total=Decimal(total_usd),
            datetime=timezone.now(),
            expires=timezone.now(),
            sales_channel=sc,
            locale=order_data.get('locale', 'en'),
        )

        attendee = order_data.get('attendee', {}) or {}
        name_parts = attendee.get('name', {}) or {}
        attendee_email = attendee.get('email') or order_data['email']
        company = attendee.get('company') or None
        country = attendee.get('country') or None

        voucher_code = order_data.get('voucher')
        voucher = _resolve_voucher(event, voucher_code) if voucher_code else None

        answers_input = order_data.get('answers', [])

        # Track the first ticket position so addons can link to it
        first_ticket_position = None

        # Add ticket positions
        for ticket in order_data.get('tickets', []):
            item_id = int(ticket.get('itemId') or ticket.get('item'))
            item = Item.objects.get(event=event, pk=item_id)
            variation_id = ticket.get('variationId') or ticket.get('variation')
            variation = None
            if variation_id:
                variation = ItemVariation.objects.filter(item=item, pk=int(variation_id)).first()
            # Use custom price if provided (voucher-discounted); otherwise item/variation default
            if ticket.get('price') is not None:
                price = Decimal(str(ticket['price']))
            elif variation and variation.default_price is not None:
                price = variation.default_price
            else:
                price = item.default_price

            qty = int(ticket.get('quantity', 1))
            # Only attach voucher to positions matching its item scope
            voucher_applies = voucher and (not voucher.item_id or voucher.item_id == item.pk)

            for _ in range(qty):
                position = OrderPosition.objects.create(
                    order=order, item=item, variation=variation, price=price,
                    attendee_name_parts=name_parts,
                    attendee_name_cached=' '.join(filter(None, [name_parts.get('given_name'), name_parts.get('family_name')])),
                    attendee_email=attendee_email,
                    company=company, country=country,
                    voucher=voucher if voucher_applies else None,
                )
                if first_ticket_position is None:
                    first_ticket_position = position
                _create_answers_for_position(position, answers_input, event, item.pk)

        # Add addon positions (linked to first ticket)
        for addon in order_data.get('addons', []) or []:
            item_id = int(addon.get('itemId') or addon.get('item'))
            item = Item.objects.get(event=event, pk=item_id)
            variation_id = addon.get('variationId') or addon.get('variation')
            variation = None
            if variation_id:
                variation = ItemVariation.objects.filter(item=item, pk=int(variation_id)).first()
            if addon.get('price') is not None:
                price = Decimal(str(addon['price']))
            elif variation and variation.default_price is not None:
                price = variation.default_price
            else:
                price = item.default_price

            qty = int(addon.get('quantity', 1))
            for _ in range(qty):
                OrderPosition.objects.create(
                    order=order, item=item, variation=variation, price=price,
                    addon_to=first_ticket_position,
                )

        # Create a walletconnect payment record
        order.payments.create(
            provider='walletconnect',
            amount=order.total,
            state='created',
        )
    return order


def record_pretix_refund(
    *, event, pretix_order_code: str, amount, refund_tx_hash: str, chain_id: int,
):
    """Create a matching Pretix OrderRefund so the refund is visible in
    Pretix's native order-detail UI (not just our custom admin page).

    We build the OrderRefund directly in state=DONE with source=external and
    attach the on-chain refund tx hash + chain in info_data. Returns the
    refund instance or None if the Pretix order / payment can't be located
    (e.g. an orphan X402CompletedOrder from before the Pretix order was
    created, which shouldn't normally happen)."""
    import json as _json
    from pretix.base.models import Order, OrderRefund
    with scopes_disabled():
        try:
            order = Order.objects.get(event=event, code=pretix_order_code)
        except Order.DoesNotExist:
            log.warning(
                '[x402 refund] no Pretix order %s to record refund against',
                pretix_order_code,
            )
            return None
        payment = order.payments.filter(provider='walletconnect', state='confirmed').first()
        if payment is None:
            log.warning(
                '[x402 refund] no confirmed walletconnect payment on order %s',
                pretix_order_code,
            )
            return None
        refund = OrderRefund.objects.create(
            order=order,
            payment=payment,
            source=OrderRefund.REFUND_SOURCE_ADMIN,
            state=OrderRefund.REFUND_STATE_DONE,
            amount=amount,
            provider='walletconnect',
            info=_json.dumps({
                'refund_tx_hash': refund_tx_hash,
                'chain_id': chain_id,
            }),
            execution_date=timezone.now(),
        )
        # Let Pretix re-evaluate whether the order is now fully refunded and
        # update its status accordingly (logs entries + notifications).
        try:
            order.create_transactions()
        except Exception as e:
            log.warning('[x402 refund] create_transactions failed for order %s: %s', order.code, e)
        return refund


def confirm_x402_payment(
    *, order, tx_hash: str, payer: str, chain_id: int, token_symbol: str,
    block_number: Optional[int] = None,
    amount: Optional[str] = None,
):
    """Mark the wc payment as confirmed and embed tx metadata in info_data.
    `block_number` and `amount` are optional — the Pretix control panel template
    hides rows with no value, so passing None just means those rows don't render.
    Returns the OrderPayment instance or None if no matching payment was found."""
    with scopes_disabled():
        payment = order.payments.filter(provider='walletconnect', state='created').first()
        if payment is None:
            log.warning(
                '[x402 confirm] no walletconnect payment in created state for order %s',
                order.code,
            )
            return None
        info = payment.info_data or {}
        info.update({
            'tx_hash': tx_hash,
            'payer': payer,
            'chain_id': chain_id,
            'token_symbol': token_symbol,
        })
        if block_number is not None:
            info['block_number'] = block_number
        if amount is not None:
            info['amount'] = amount
        payment.info_data = info
        payment.save()
        payment.confirm()
        return payment
