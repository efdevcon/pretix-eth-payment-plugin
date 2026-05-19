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
from collections import defaultdict
from decimal import Decimal
from typing import Optional
from django.db import transaction
from django.utils import timezone
from django_scopes import scopes_disabled

log = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised by `_check_and_lock_quotas` when the order would oversell a
    Pretix Quota. Surfaced to the verify endpoint so it can roll back the
    payment claim and return a distinctive error to the buyer."""
    def __init__(self, item_name: str, requested: int, available: int):
        self.item_name = item_name
        self.requested = requested
        self.available = available
        super().__init__(
            f'quota exceeded for {item_name}: requested {requested}, available {available}'
        )


class VoucherUnavailableError(Exception):
    """Raised when a voucher fails revalidation at order-create time —
    expired between purchase and verify, or `redeemed >= max_usages` because
    another buyer's order claimed the last slot. The purchase endpoint runs
    `check_voucher(..., lock=False)` as a pre-payment fail-fast; the
    create_pretix_order path runs `check_voucher(..., lock=True)` inside the
    atomic block to actually serialize concurrent redemption."""
    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(f"voucher '{code}' unavailable: {reason}")


def check_voucher(event, voucher_code, *, lock: bool):
    """Resolve and revalidate a voucher. Returns the Voucher instance, or
    None when no code was provided. Raises VoucherUnavailableError if the
    voucher doesn't exist, has expired, or has been fully redeemed.

    `lock=True` takes a row-level lock (`SELECT ... FOR UPDATE`) for the
    surrounding transaction so concurrent x402 (and native Pretix) orders
    can't both pass a `redeemed < max_usages` check and double-redeem a
    voucher with `max_usages=1`. `lock=False` is for fail-fast at purchase
    time — it gives a snapshot answer without holding any lock.

    Note: `Voucher.redeemed` is maintained by Pretix via signals on
    OrderPosition save, so by the time we re-read it inside the locked
    transaction it reflects every prior committed redemption.
    """
    if not voucher_code:
        return None
    from pretix.base.models import Voucher
    qs = Voucher.objects.filter(event=event, code__iexact=voucher_code)
    if lock:
        qs = qs.select_for_update()
    voucher = qs.first()
    if voucher is None:
        raise VoucherUnavailableError(voucher_code, 'not found')
    if voucher.valid_until and timezone.now() > voucher.valid_until:
        raise VoucherUnavailableError(voucher_code, 'expired')
    if voucher.max_usages and (voucher.redeemed or 0) >= voucher.max_usages:
        raise VoucherUnavailableError(voucher_code, 'fully redeemed')
    return voucher


def check_quotas(event, items_with_qty, *, lock: bool):
    """Verify there's enough availability in every relevant Quota to satisfy
    `items_with_qty`. When `lock=True`, the rows are locked for the duration
    of the surrounding transaction (`SELECT ... FOR UPDATE`) so concurrent
    x402 create_pretix_order calls (and native Pretix checkout, which uses
    the same Quota rows) can't oversell. Locks are taken in deterministic PK
    order to prevent deadlocks across overlapping quota sets.

    `lock=False` is for pre-payment fail-fast: it gives a snapshot answer
    without holding any lock — useful at the `purchase` endpoint so a buyer
    requesting more than the remaining stock doesn't get a payment quote in
    the first place. The lock-based call inside `create_pretix_order` is the
    real race-tight enforcement.

    items_with_qty: iterable of (Item, ItemVariation | None, qty: int).
    Raises QuotaExceededError on the first quota that can't satisfy the request.
    Quotas with `size=None` (unlimited) are skipped.
    """
    from pretix.base.models import Quota

    requested_per_quota = defaultdict(int)
    item_name_per_quota = {}
    for item, variation, qty in items_with_qty:
        if qty <= 0:
            continue
        qs = variation.quotas.all() if variation is not None else item.quotas.all()
        for q in qs:
            requested_per_quota[q.pk] += qty
            item_name_per_quota.setdefault(q.pk, str(item.name))

    if not requested_per_quota:
        return

    sorted_pks = sorted(requested_per_quota.keys())
    base_qs = Quota.objects.filter(pk__in=sorted_pks)
    if lock:
        base_qs = base_qs.select_for_update()
    quotas = list(base_qs)

    for quota in quotas:
        # `count_waitinglist=False` matches the catalog-fetch check at
        # views_x402.get_ticket_purchase_info; we don't reserve units for
        # waiting-list buyers from the x402 path.
        state, remaining = quota.availability(count_waitinglist=False)
        # `remaining` is None when the quota is unlimited (`Quota.size is None`).
        if remaining is None:
            continue
        requested = requested_per_quota[quota.pk]
        if remaining < requested:
            raise QuotaExceededError(
                item_name=item_name_per_quota.get(quota.pk, 'item'),
                requested=requested,
                available=max(0, remaining),
            )


def _check_and_lock_quotas(event, items_with_qty):
    """Race-tight quota check used inside `create_pretix_order`'s atomic block.
    Thin wrapper over `check_quotas` with `lock=True`."""
    check_quotas(event, items_with_qty, lock=True)


# `_resolve_voucher` was removed — it returned a Voucher without checking
# expiration or `max_usages`, and didn't take a row lock. `check_voucher`
# (above) is the replacement: it raises VoucherUnavailableError on stale or
# exhausted codes and supports `lock=True` for race-tight revalidation.


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
        # Resolve every (Item, variation, qty) triple in the order up front so
        # we can lock the relevant Quota rows BEFORE any OrderPosition is
        # written. Without this lock+check, two concurrent x402 orders for the
        # last unit can both succeed (each `OrderPosition.objects.create` is a
        # blind insert that doesn't decrement quota), and the catalog
        # `available` flag computed at page-load is a stale snapshot. Fixed
        # ordering of locks (by Quota PK in the helper) prevents deadlocks.
        items_with_qty = []
        for ticket in order_data.get('tickets', []) or []:
            item_id = int(ticket.get('itemId') or ticket.get('item'))
            item = Item.objects.get(event=event, pk=item_id)
            variation_id = ticket.get('variationId') or ticket.get('variation')
            variation = (
                ItemVariation.objects.filter(item=item, pk=int(variation_id)).first()
                if variation_id else None
            )
            items_with_qty.append((item, variation, int(ticket.get('quantity', 1))))
        for addon in order_data.get('addons', []) or []:
            item_id = int(addon.get('itemId') or addon.get('item'))
            item = Item.objects.get(event=event, pk=item_id)
            variation_id = addon.get('variationId') or addon.get('variation')
            variation = (
                ItemVariation.objects.filter(item=item, pk=int(variation_id)).first()
                if variation_id else None
            )
            items_with_qty.append((item, variation, int(addon.get('quantity', 1))))
        _check_and_lock_quotas(event, items_with_qty)

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

        # Lock-and-revalidate the voucher inside the atomic block. Holding the
        # `SELECT ... FOR UPDATE` lock for the rest of the transaction
        # serializes concurrent redemptions so two buyers using the same
        # `max_usages=1` voucher can't both succeed. Raises
        # VoucherUnavailableError if expired or exhausted; the verify endpoint
        # surfaces that as a 409 with a distinctive category.
        voucher_code = order_data.get('voucher')
        voucher = check_voucher(event, voucher_code, lock=True)

        # Quantity-multiplier guard: a single voucher attached to qty=N
        # positions of its target item gets redeemed N times by Pretix's
        # post-save signals when this transaction commits. Without this
        # check, a buyer could submit `tickets:[{itemId, quantity:10}]` with
        # a max_usages=1 voucher and have the discount apply to all 10
        # positions. The lock acquired by check_voucher() above is held for
        # the rest of this transaction, so concurrent orders can't slip in
        # between us reading `redeemed` and finishing the writes.
        if voucher is not None and voucher.max_usages:
            voucher_uses_in_cart = sum(
                int(t.get('quantity', 1))
                for t in (order_data.get('tickets', []) or [])
                if voucher.item_id is None or voucher.item_id == int(t.get('itemId') or t.get('item'))
            )
            if voucher_uses_in_cart > 0:
                remaining = voucher.max_usages - (voucher.redeemed or 0)
                if voucher_uses_in_cart > remaining:
                    raise VoucherUnavailableError(
                        voucher_code,
                        f'cart needs {voucher_uses_in_cart} use(s), only {max(0, remaining)} remaining',
                    )

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
        #
        # `info` carries the machine-readable refund metadata (used by the
        # plugin's Pretix-native UI render hook). `comment` mirrors it as
        # human-readable text — that mirror is needed because Pretix's
        # REST API `/orders/<code>/` strips `info` from embedded refunds
        # but exposes `comment` as-is, so storefront / buyer-recap code
        # that reads the order JSON can recover the on-chain tx hash by
        # regex over the comment URL.
        from pretix_eth.chains import CHAIN_METADATA
        chain_meta = CHAIN_METADATA.get(chain_id) or {}
        explorer_tx_base = chain_meta.get('explorer_url')
        explorer_link = (
            f'{explorer_tx_base}{refund_tx_hash}'
            if explorer_tx_base else refund_tx_hash
        )
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
            comment=f'Crypto refund issued on-chain: {explorer_link}',
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
                log.info(
                    '[x402 refund] cancel_order skipped for %s (refund still recorded): %s',
                    order.code, e,
                )

        # Best-effort buyer notification. Pretix doesn't ship a built-in
        # "refund issued" email, so we send our own — mirrors the
        # information layout from `order_pending_mail_render` (the
        # `{payment_info}` block in the order-paid email) so the buyer
        # can see the on-chain refund tx hash + chain explorer link
        # without checking the order recap page. Failure is logged and
        # swallowed — the refund itself is already on-chain + recorded,
        # an email blip shouldn't surface as a 5xx to the admin tool.
        try:
            _send_refund_email(order, amount, refund_tx_hash, chain_id)
        except Exception as e:
            log.warning(
                '[x402 refund] notification email failed for %s (refund still recorded): %s',
                order.code, e,
            )
        return refund


def _send_refund_email(order, amount, refund_tx_hash: str, chain_id: int):
    """Send a notification email to the buyer when a manual refund is
    issued. Uses Pretix's `pretix.base.services.mail.mail()` so the
    email goes through the event's configured SMTP + sender, gets
    logged on the order, and respects locale conventions. Skipped
    silently if the order has no email recorded."""
    from pretix.base.services.mail import mail
    from i18nfield.strings import LazyI18nString
    from pretix_eth.chains import CHAIN_METADATA
    if not getattr(order, 'email', None):
        return
    chain_meta = CHAIN_METADATA.get(chain_id) or {}
    explorer_tx_base = chain_meta.get('explorer_url')
    chain_name = chain_meta.get('name') or f'chain {chain_id}'
    tx_url = (
        f'{explorer_tx_base}{refund_tx_hash}' if explorer_tx_base
        else refund_tx_hash
    )

    # Order detail URL. Prefer the plugin's `frontend_order_url_template`
    # (the same setting that powers the {url} mail placeholder in signals.py)
    # so refund emails link into the storefront's order page. Fall back to
    # Pretix's presale URL if the operator hasn't configured one.
    order_url = ''
    try:
        from pretix_eth.payment import WalletConnectPayment
        provider = WalletConnectPayment(order.event)
        template = (provider.settings.get('frontend_order_url_template') or '').strip()
        if template:
            order_url = template.replace('{code}', order.code).replace('{secret}', order.secret)
    except Exception:
        pass
    if not order_url:
        try:
            from pretix.multidomain.urlreverse import build_absolute_uri
            order_url = build_absolute_uri(
                order.event,
                'presale:event.order',
                kwargs={'order': order.code, 'secret': order.secret},
            )
        except Exception:
            order_url = ''

    # Pretix's `mail()` treats a plain `str` template as a Django
    # template *filename*. To pass inline body text instead, wrap it
    # in `LazyI18nString` — that's the documented hook for the
    # `format_map(template, context)` path (see the docstring on
    # `pretix.base.services.mail.mail`). The context dict carries the
    # values referenced as `{placeholder}` markers in the body.
    # Pretix renders the body through `markdown_compile_email` for the
    # HTML version, which collapses single newlines into a space. Use
    # `\n\n` (paragraph break) between each detail row so they render
    # as separate lines in both the HTML and plain-text variants.
    # Same convention `order_pending_mail_render` uses for the
    # `{payment_info}` block.
    body_template = LazyI18nString(
        'Hello,\n\n'
        'A refund of {amount} {currency} has been issued for your order {order}.\n\n'
        'You can view the details of your refund below.\n\n'
        '---\n\n'
        '**Refund details**\n\n'
        'Amount: {amount} {currency}\n\n'
        'Network: {chain_name}\n\n'
        'Transaction: [View transaction]({tx_url})\n\n'
        '[View order details]({url})\n\n'
        '---\n\n'
        'The funds were returned to the wallet that originally paid. '
        'If you don\'t see the transfer or have any questions, please reply '
        'to this email.\n\n'
        'Best regards,\n\n'
        '{event} team 🚀'
    )
    mail(
        email=order.email,
        subject=LazyI18nString('Refund issued for order {order}'),
        template=body_template,
        context={
            'order': order.code,
            'amount': str(amount),
            'currency': order.event.currency,
            'chain_name': chain_name,
            'tx_url': tx_url,
            'url': order_url,
            'event': str(order.event.name),
        },
        event=order.event,
        order=order,
        locale=getattr(order, 'locale', None) or order.event.settings.locale,
        auto_email=True,
    )


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
