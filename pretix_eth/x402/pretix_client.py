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
from django.db import transaction
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
    from pretix.base.models import Order, OrderPosition, OrderFee, Item, ItemVariation
    # Pretix requires Order/OrderPosition/OrderFee writes to happen inside an
    # atomic block — otherwise its transaction-ledger bookkeeping warns
    # ("... however you are not doing it inside a database transaction!").
    with scopes_disabled(), transaction.atomic():
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
            # Propagate the event's test mode flag onto the order. Without this,
            # x402-created orders default to testmode=False even on test events
            # (the wc_inject flow gets this for free via Pretix's native
            # checkout; we have to set it explicitly because we instantiate
            # Order ourselves). On-chain verification still runs regardless —
            # this is purely an admin/accounting flag.
            testmode=getattr(event, 'testmode', False),
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

            # Pretix's `ItemAddOn.price_included` flag means: when this addon is
            # bought as a child of the parent ticket, the addon is free regardless
            # of its standalone default_price. Native Pretix checkout enforces this
            # automatically; we must enforce it here too because we instantiate
            # OrderPosition directly. Without this, a "free with ticket" scarf
            # would be charged at its $X default_price.
            if first_ticket_position is not None and item.category_id is not None:
                addon_link = first_ticket_position.item.addons.filter(
                    addon_category=item.category_id,
                ).first()
                if addon_link and addon_link.price_included:
                    price = Decimal('0.00')

            qty = int(addon.get('quantity', 1))
            for _ in range(qty):
                OrderPosition.objects.create(
                    order=order, item=item, variation=variation, price=price,
                    addon_to=first_ticket_position,
                )

        # Mirror the wc-native checkout: surface `crypto_discount_percent` as a
        # negative OrderFee (fee_type='payment'). The Order's `total` was set
        # explicitly above to the already-discounted amount, so this fee is
        # purely cosmetic — positions(sum) + fee(-discount) == order.total.
        # Without this row, x402 orders would have no on-Order trace of the
        # discount; the Pretix admin would only see positions summing to
        # subtotal but order.total mysteriously lower. With it, the order page
        # shows "Payment fee: -$X.XX" identical to the wc path.
        crypto_discount_str = order_data.get('crypto_discount')
        if crypto_discount_str:
            try:
                crypto_discount_dec = Decimal(str(crypto_discount_str))
            except Exception:
                crypto_discount_dec = Decimal('0')
            if crypto_discount_dec > 0:
                OrderFee.objects.create(
                    order=order,
                    fee_type=OrderFee.FEE_TYPE_PAYMENT,
                    value=-crypto_discount_dec,
                    description='',
                    tax_rate=Decimal('0.00'),
                    tax_value=Decimal('0.00'),
                )

        # Create a walletconnect payment record
        order.payments.create(
            provider='walletconnect',
            amount=order.total,
            state='created',
        )

        # Pretix's inventory/accounting bookkeeping is kept in a `Transaction`
        # table that tracks every position/fee change. Creating positions and
        # fees via direct ORM calls (as we do above) leaves the order "dirty"
        # from Pretix's perspective; without this call Pretix logs a WARNING
        # with a full stack trace on every order. `is_new=True` tells it this
        # is the initial transaction set for the order.
        order.create_transactions(is_new=True)
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
    from decimal import Decimal
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
        # Create the refund in CREATED state, then call .done() — that path
        # logs the action and, critically, flips payment.state to REFUNDED
        # when the refund amount fully covers the payment. Creating directly
        # in state=DONE skips that logic.
        refund = OrderRefund.objects.create(
            order=order,
            payment=payment,
            source=OrderRefund.REFUND_SOURCE_ADMIN,
            state=OrderRefund.REFUND_STATE_CREATED,
            amount=Decimal(amount),
            provider='walletconnect',
            info=_json.dumps({
                'refund_tx_hash': refund_tx_hash,
                'chain_id': chain_id,
            }),
        )
        refund.done()

        # Cancel the order when this refund covers the full payment — so the
        # Pretix order status flips away from PAID and the UI reflects reality.
        # Partial refunds are left alone (order stays PAID, payment stays in
        # its new REFUNDED state).
        if payment.refunded_amount >= payment.amount:
            try:
                from pretix.base.services.orders import _cancel_order
                _cancel_order(
                    order, user=None, send_mail=False,
                    cancellation_fee=Decimal('0'), cancel_invoice=True,
                )
            except Exception as e:
                log.warning(
                    '[x402 refund] cancel_order failed for %s (refund still recorded): %s',
                    order.code, e,
                )
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

        # Render the payment recap for the order-paid email. Pretix's paid
        # email template uses the {payment_info} placeholder, which — unlike
        # the placed email — does NOT call `order_pending_mail_render`; it
        # reads directly from the `mail_text` kwarg passed into `.confirm()`.
        # Compute the recap here from the info we just populated and pass it
        # through so the buyer gets amount/network/tx in their paid email.
        try:
            from pretix_eth.payment import WalletConnectPayment
            provider = WalletConnectPayment(order.event)
            mail_text = provider.order_pending_mail_render(order, payment)
        except Exception as e:
            log.warning('[x402 confirm] failed to render mail_text for %s: %s', order.code, e)
            mail_text = ''

        payment.confirm(mail_text=mail_text)
        return payment
