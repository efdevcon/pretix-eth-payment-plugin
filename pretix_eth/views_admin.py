"""x402 admin endpoints — orders list, stats, refund actions."""
import json
import logging
import re
from decimal import Decimal
from typing import Optional

from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_scopes import scopes_disabled

from pretix_eth.models import (
    WCPaymentAttempt, X402CompletedOrder, X402PendingOrder,
)
from pretix_eth.x402.auth import require_pretix_admin_token
from pretix_eth.x402 import ticketstore

log = logging.getLogger(__name__)


_CAMEL_TO_SNAKE_ADMIN = {
    'paymentReference': 'payment_reference',
    'adminAddress': 'admin_address',
    'refundTxHash': 'refund_tx_hash',
    'txHash': 'tx_hash',
    'chainId': 'chain_id',
    'ethPayerSignature': 'eth_payer_signature',
    'orderCode': 'order_code',
    'orderSecret': 'order_secret',
    'overrideQuoteWindow': 'override_quote_window',
    'overrideNoQuote': 'override_no_quote',
    'quoteId': 'quote_id',
}


def _truthy(v) -> bool:
    return v is True or str(v or '').strip().lower() in ('1', 'true', 'yes')


def _recover_wc_quote(order):
    """Most-recent WalletConnect quote (raw dict) carrying an ``intended_payer``
    from ANY of the order's walletconnect payments (created + canceled), newest
    first — or ``None``.

    Buyers retry a lot: Pretix cancels the old WC payment and creates a fresh
    ``created`` one on each attempt, and that fresh payment usually holds only a
    challenge nonce with NO quote. The real quote therefore lives on a now-
    canceled payment. This mirrors the unpaid-list view's scan so the manual
    verify binds to the buyer's real quote instead of only the current payment.
    """
    wc_payments = sorted(
        (p for p in order.payments.all() if p.provider == 'walletconnect'),
        key=lambda p: p.created or order.datetime,
        reverse=True,
    )
    for p in wc_payments:
        q = (p.info_data or {}).get('quote') or {}
        if q.get('intended_payer'):
            return q
    return None


def _find_wc_quote(order, quote_id: str):
    """The order's WC quote with this exact ``quote_id`` (across all payments), or
    ``None``. Lets the admin pick the specific attempt matching the real on-chain
    payment when a buyer created several quotes (different wallet/token/amount)."""
    for p in order.payments.all():
        if p.provider != 'walletconnect':
            continue
        q = (p.info_data or {}).get('quote') or {}
        if q.get('quote_id') == quote_id:
            return q
    return None


def _read_body(request) -> dict:
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return {}
    if isinstance(body, dict):
        for camel, snake in _CAMEL_TO_SNAKE_ADMIN.items():
            if camel in body and snake not in body:
                body[snake] = body[camel]
    return body


@scopes_disabled()
def _get_event(org_slug: str, event_slug: str):
    from pretix.base.models import Event
    try:
        return Event.objects.get(slug=event_slug, organizer__slug=org_slug)
    except Event.DoesNotExist:
        return None


def _check_event_access_or_403(request, event):
    """Final cross-tenant authorization check on the body-resolved event.

    The `require_pretix_admin_token` decorator validates token+team against
    the URL-resolved event (`?organizer=…&event=…`). Views that re-resolve
    the event from the JSON body must call this so a URL/body mismatch can't
    bypass authorization (e.g. URL targets org A to pass the decorator,
    body targets org B to act on its data).

    Returns a `JsonResponse(403)` on mismatch, or None when access is OK.
    """
    from pretix_eth.x402.auth import check_team_event_access
    if not check_team_event_access(request, event):
        return JsonResponse(
            {'success': False, 'error': 'forbidden — token does not cover this event'},
            status=403,
        )
    return None


def _serialize_completed(
    o: X402CompletedOrder,
    email: Optional[str] = None,
    pretix_status: Optional[str] = None,
    pretix_testmode: Optional[bool] = None,
    pretix_total: Optional[Decimal] = None,
    overpaid_usd: Optional[str] = None,
    refunded_amount: Optional[str] = None,
) -> dict:
    return {
        'source': 'x402',
        'paymentReference': o.payment_reference,
        'txHash': o.tx_hash,
        'pretixOrderCode': o.pretix_order_code,
        'payer': o.payer,
        'completedAt': int(o.completed_at.timestamp()),
        'chainId': o.chain_id,
        'totalUsd': str(o.total_usd),
        'tokenSymbol': o.token_symbol,
        'cryptoAmount': o.crypto_amount,
        'gasCostWei': o.gas_cost_wei,
        'email': email,
        'refundStatus': o.refund_status,
        'refundTxHash': o.refund_tx_hash,
        'refundMeta': o.refund_meta or {},
        # Pretix order state mirror — `n` pending, `p` paid, `e` expired,
        # `c` canceled. `None` when the matching Pretix Order couldn't
        # be loaded (rare — admin row points at a Pretix code that's
        # since been deleted).
        'pretixStatus': pretix_status,
        'pretixTestmode': pretix_testmode if pretix_testmode is not None else False,
        'pretixTotal': str(pretix_total) if pretix_total is not None else None,
        'overpaidUsd': overpaid_usd,
        # Sum of Pretix OrderRefunds in DONE state on the matched order.
        # Drives the "Refunded $X" badge + button-suppression in the
        # admin UI. Includes refunds applied via *any* path (plugin's
        # x402 refund flow, plugin's WC refund flow, Pretix-native UI).
        'refundedAmount': refunded_amount,
    }


def _serialize_wc_attempt(
    w: WCPaymentAttempt, total: Optional[Decimal], payment_info: Optional[dict] = None,
    email: Optional[str] = None,
    pretix_status: Optional[str] = None,
    pretix_testmode: Optional[bool] = None,
    overpaid_usd: Optional[str] = None,
    refunded_amount: Optional[str] = None,
    refund_tx_hash: Optional[str] = None,
) -> dict:
    """Legacy (pre-x402) WalletConnect direct-send flow. Completed row means
    the tx hash was verified on-chain and the Pretix order confirmed.

    `WCPaymentAttempt` itself doesn't carry `token_symbol` or raw amount, but the
    verify handler in `views.py` mirrors that data onto the matching Pretix
    `OrderPayment.info_data` at the same time. `payment_info` is that dict;
    we read token_symbol + amount from it when available so the admin UI can
    display accurate values instead of guessing."""
    info = payment_info or {}
    token_symbol = info.get('token_symbol')
    # info['amount'] on legacy rows may be "<int> (raw)"; strip the suffix.
    crypto_amount = info.get('amount')
    if isinstance(crypto_amount, str) and crypto_amount.strip().endswith('(raw)'):
        crypto_amount = crypto_amount.strip()[:-len('(raw)')].strip()
    return {
        'source': 'wc_attempt',
        'paymentReference': w.quote_id,
        'txHash': w.tx_hash,
        'pretixOrderCode': w.order_code,
        'payer': w.payer,
        'completedAt': int(w.created_at.timestamp()) if w.created_at else None,
        'chainId': w.chain_id,
        'totalUsd': str(total) if total is not None else None,
        'tokenSymbol': token_symbol,
        'cryptoAmount': crypto_amount if crypto_amount else None,
        'email': email,
        # Pretix-side state mirror. `overpaid_usd` and `refunded_amount`
        # are both computed from Pretix payments/refunds at the call
        # site so the same logic catches cancelled-but-unrefunded and
        # already-refunded rows for legacy WC orders too.
        'pretixStatus': pretix_status,
        'pretixTestmode': pretix_testmode if pretix_testmode is not None else False,
        'pretixTotal': str(total) if total is not None else None,
        'overpaidUsd': overpaid_usd,
        'refundedAmount': refunded_amount,
        'refundTxHash': refund_tx_hash,
    }


def _serialize_pending(o: X402PendingOrder, pretix_testmode: Optional[bool] = None) -> dict:
    order_data = o.order_data or {}
    addons = order_data.get('addons') or []
    addon_ids = [a.get('item', {}).get('id') for a in addons if isinstance(a, dict)]
    return {
        'paymentReference': o.payment_reference,
        'createdAt': int(o.created_at.timestamp()),
        'expiresAt': int(o.expires_at.timestamp()),
        'intendedPayer': o.intended_payer,
        'totalUsd': str(o.total_usd),
        'expectedChainId': o.expected_chain_id,
        # Pending rows are pre-order-creation, so they don't have a
        # Pretix Order to mirror state from — `testmode` is the event-
        # level flag instead, telling the admin "this attempt was made
        # against the test catalog".
        'pretixTestmode': pretix_testmode if pretix_testmode is not None else False,
        # Pre-computed ETH wei per chain (snapshot at pending creation time —
        # locks in the rate the buyer was quoted). Stables aren't pre-stored
        # because their amount is just `total_usd * 10^6`.
        'expectedEthAmountWeiByChain': o.expected_eth_amount_wei_by_chain or {},
        'metadata': {
            **(o.metadata or {}),
            **({'addonIds': [i for i in addon_ids if i is not None]} if addon_ids else {}),
            **({'voucher': order_data['voucher']} if order_data.get('voucher') else {}),
        },
    }


@csrf_exempt
@require_http_methods(['GET'])
@require_pretix_admin_token('can_view_orders')
def admin_orders(request: HttpRequest, **kwargs):
    org = request.GET.get('organizer', '')
    event_slug = request.GET.get('event', '')
    event = _get_event(org, event_slug)
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer

    from django.db.models import Sum, Count
    from django.db.utils import ProgrammingError
    from pretix.base.models import Order
    with scopes_disabled():
        completed_qs = X402CompletedOrder.objects.filter(event=event)
        pending_qs = X402PendingOrder.objects.filter(event=event)
        x402_completed_list = list(completed_qs.order_by('-completed_at')[:500])

        # Single round-trip to fetch all relevant Pretix Orders + their
        # payment/refund children. The admin UI needs buyer email, order
        # state, testmode flag, and refund-owed delta. `.only(...)` on
        # the main query skips Order's wide payload (~30+ columns
        # including meta_info JSON, attendee data); `.prefetch_related`
        # pulls the payment + refund children in two extra queries
        # (one per relation), still avoiding the per-row N+1.
        from pretix.base.models import OrderRefund
        x402_codes = {o.pretix_order_code for o in x402_completed_list if o.pretix_order_code}
        email_by_code: dict = {}
        order_meta_by_code: dict = {}
        if x402_codes:
            for porder in (
                Order.objects.filter(event=event, code__in=x402_codes)
                .prefetch_related('payments', 'refunds')
                .only('code', 'email', 'status', 'testmode', 'total')
            ):
                email_by_code[porder.code] = porder.email
                # "Refund owed" = paid in - refunded out - effective owed.
                # For cancelled orders, effective_owed is 0 (the org owes
                # back everything net of refunds — the order delivered
                # nothing). For active orders it's the order total —
                # buyer paid more than the order owes (overpayment).
                paid_in = Decimal('0')
                refunded_out = Decimal('0')
                try:
                    for p in porder.payments.all():
                        # `confirmed` = paid and not yet refunded;
                        # `refunded` = paid then fully refunded — the
                        # matching refund(s) will be in refunds_out
                        # below, so counting these here keeps the net
                        # math correct (paid_in - refunded_out = 0 for
                        # a clean paid-then-refunded round-trip).
                        if getattr(p, 'state', None) in ('confirmed', 'refunded'):
                            paid_in += Decimal(p.amount or 0)
                    for r in porder.refunds.all():
                        # Use the OrderRefund constant instead of the
                        # bare 'done' string so a Pretix rename of the
                        # state vocabulary doesn't silently zero us.
                        if getattr(r, 'state', None) == OrderRefund.REFUND_STATE_DONE:
                            refunded_out += Decimal(r.amount or 0)
                except Exception as e:
                    log.warning('[x402 admin] payment/refund agg failed for %s: %s', porder.code, e)
                net_paid = paid_in - refunded_out
                effective_owed = Decimal('0') if porder.status == 'c' else Decimal(porder.total or 0)
                # Quantize first, then check > 0. Avoids the off-by-one
                # where a $0.01-exactly delta fell through `> Decimal('0.01')`
                # — a real case we hit on a test order with $0.01 total.
                refund_owed = (net_paid - effective_owed).quantize(Decimal('0.01'))
                overpaid_usd = str(refund_owed) if refund_owed > Decimal('0') else None
                refunded_qd = refunded_out.quantize(Decimal('0.01'))
                refunded_amount = str(refunded_qd) if refunded_qd > Decimal('0') else None
                order_meta_by_code[porder.code] = {
                    'status': porder.status,
                    'testmode': bool(porder.testmode),
                    'total': porder.total,
                    'overpaid_usd': overpaid_usd,
                    'refunded_amount': refunded_amount,
                }

        x402_rows = [
            _serialize_completed(
                o,
                email=email_by_code.get(o.pretix_order_code),
                pretix_status=(order_meta_by_code.get(o.pretix_order_code) or {}).get('status'),
                pretix_testmode=(order_meta_by_code.get(o.pretix_order_code) or {}).get('testmode'),
                pretix_total=(order_meta_by_code.get(o.pretix_order_code) or {}).get('total'),
                overpaid_usd=(order_meta_by_code.get(o.pretix_order_code) or {}).get('overpaid_usd'),
                refunded_amount=(order_meta_by_code.get(o.pretix_order_code) or {}).get('refunded_amount'),
            )
            for o in x402_completed_list
        ]
        # `event.testmode` is the catalog-level flag — pending rows are
        # created before any Pretix Order exists, so this is the only
        # signal that an attempt was a test.
        event_testmode = bool(getattr(event, 'testmode', False))
        pending = [_serialize_pending(o, pretix_testmode=event_testmode) for o in pending_qs.order_by('-created_at')[:200]]

        # Legacy pre-x402 WalletConnect direct-send rows are merged into
        # `completed` with `source='wc_attempt'` so the unified admin table
        # can show them. Daimo-era SignedMessage rows are intentionally
        # excluded — they predate all the current flows and aren't useful
        # operational data for today's admins.
        legacy_wc: list = []
        try:
            wc_attempts = list(
                WCPaymentAttempt.objects
                .filter(state=WCPaymentAttempt.STATE_COMPLETED)
                .only('id', 'tx_hash', 'quote_id', 'order_code', 'payer', 'chain_id', 'state', 'created_at')
                .order_by('-created_at')[:500]
            )
            wc_codes = {w.order_code for w in wc_attempts}
            # `.only(...)` + `.prefetch_related(...)`: read the wide-payload
            # columns we need plus the payment/refund children for the
            # refund-owed computation. Same shape as the x402 fetch above.
            wc_overpaid_by_code: dict = {}
            wc_refunded_by_code: dict = {}
            # Mirror of refund_tx_hash for wc_attempt rows so the admin UI
            # can render the explorer link on the Refunded badge. The tx
            # hash is stored on `OrderRefund.info` JSON by
            # `record_pretix_refund`; we extract the most recent DONE
            # refund's hash here (typical case: one refund per order).
            wc_refund_tx_by_code: dict = {}
            orders_by_code = {}
            if wc_codes:
                for porder in (
                    Order.objects.filter(event=event, code__in=wc_codes)
                    .prefetch_related('payments', 'refunds')
                    .only('code', 'email', 'total', 'status', 'testmode')
                ):
                    orders_by_code[porder.code] = porder
                    paid_in = Decimal('0')
                    refunded_out = Decimal('0')
                    try:
                        for p in porder.payments.all():
                            # Same state filter as the x402 path above —
                            # see comment there for the `refunded` rationale.
                            if getattr(p, 'state', None) in ('confirmed', 'refunded'):
                                paid_in += Decimal(p.amount or 0)
                        for r in porder.refunds.all():
                            if getattr(r, 'state', None) == OrderRefund.REFUND_STATE_DONE:
                                refunded_out += Decimal(r.amount or 0)
                                # Extract the on-chain refund tx hash from the
                                # OrderRefund.info JSON (set by
                                # record_pretix_refund). Last-wins captures
                                # the most recently DONE refund's hash, which
                                # is the right one to surface in the UI when
                                # multiple refunds exist on the same order.
                                try:
                                    info_raw = r.info or ''
                                    info_obj = json.loads(info_raw) if isinstance(info_raw, str) and info_raw else (r.info_data or {})
                                    tx = info_obj.get('refund_tx_hash')
                                    if tx:
                                        wc_refund_tx_by_code[porder.code] = tx
                                except (ValueError, TypeError):
                                    pass
                    except Exception as e:
                        log.warning('[wc admin] payment/refund agg failed for %s: %s', porder.code, e)
                    net_paid = paid_in - refunded_out
                    effective_owed = Decimal('0') if porder.status == 'c' else Decimal(porder.total or 0)
                    refund_owed = (net_paid - effective_owed).quantize(Decimal('0.01'))
                    wc_overpaid_by_code[porder.code] = str(refund_owed) if refund_owed > Decimal('0') else None
                    refunded_qd = refunded_out.quantize(Decimal('0.01'))
                    wc_refunded_by_code[porder.code] = str(refunded_qd) if refunded_qd > Decimal('0') else None
            for code, order in orders_by_code.items():
                email_by_code.setdefault(code, order.email)
            # The legacy verify handler (views.py) writes token_symbol + amount
            # into the matching Pretix OrderPayment.info_data by tx_hash. Pull
            # that side so the admin UI can show accurate token + amount.
            # Filter by `order__code__in=wc_codes` so we don't scan every
            # walletconnect payment in the event — events with many wc_inject
            # orders previously paid O(all walletconnect payments) just to find
            # the few that match this batch's tx_hashes.
            from pretix.base.models import OrderPayment
            payments_by_tx: dict = {}
            if wc_attempts:
                tx_hashes = {w.tx_hash for w in wc_attempts}
                for p in OrderPayment.objects.filter(
                    order__event=event, provider='walletconnect',
                    order__code__in=wc_codes,
                ).only('id', 'info'):
                    info = p.info_data or {}
                    tx = info.get('tx_hash')
                    if tx in tx_hashes:
                        payments_by_tx[tx] = info
            legacy_wc = [
                _serialize_wc_attempt(
                    w,
                    total=orders_by_code[w.order_code].total if w.order_code in orders_by_code else None,
                    payment_info=payments_by_tx.get(w.tx_hash),
                    email=email_by_code.get(w.order_code),
                    pretix_status=orders_by_code[w.order_code].status if w.order_code in orders_by_code else None,
                    pretix_testmode=bool(orders_by_code[w.order_code].testmode) if w.order_code in orders_by_code else None,
                    overpaid_usd=wc_overpaid_by_code.get(w.order_code),
                    refunded_amount=wc_refunded_by_code.get(w.order_code),
                    refund_tx_hash=wc_refund_tx_by_code.get(w.order_code),
                )
                for w in wc_attempts if w.order_code in orders_by_code
            ]
        except ProgrammingError as e:
            log.warning('WCPaymentAttempt schema drift, skipping legacy rows: %s', e)

        completed = sorted(
            x402_rows + legacy_wc,
            key=lambda r: r.get('completedAt') or 0,
            reverse=True,
        )

        # Unpaid wc_inject orders: Pretix orders in 'pending' state with a
        # walletconnect OrderPayment in `created` state and NO completed
        # WCPaymentAttempt yet. These are the candidates for manual verify
        # (admin pastes a recovered tx hash). Excludes orders the auto-flow
        # already finished — those land in `completed` via wc_attempt above.
        wc_unpaid: list = []
        try:
            already_completed_codes = {w.order_code for w in wc_attempts}
            wc_unpaid_qs = (
                Order.objects
                .filter(
                    event=event,
                    status=Order.STATUS_PENDING,
                    payments__provider='walletconnect',
                    payments__state='created',
                )
                .distinct()
                .prefetch_related('payments')
                .only('code', 'secret', 'email', 'total', 'datetime', 'status', 'testmode')
                .order_by('-datetime')[:200]
            )
            for porder in wc_unpaid_qs:
                if porder.code in already_completed_codes:
                    continue
                # Surface the most recent quote (if any) so the manual-verify
                # modal can pre-fill chain + symbol + payer from what the
                # buyer originally signed. Admin can override any of these.
                #
                # The quote lives per-OrderPayment. When a buyer retries,
                # Pretix cancels the old payment and creates a fresh
                # `created` one — which often has only a challenge nonce and
                # no quote yet. So we scan ALL walletconnect payments
                # (created + canceled), newest first, and take the first
                # one carrying a quote. That recovers the buyer's last real
                # selection even when it lives on a now-superseded payment.
                # Collect ALL quotes across the order's WC payments (newest first)
                # so the manual-verify modal can show a picker — a buyer who
                # retried with different wallets/tokens leaves several quotes with
                # different payers/amounts. `quote` (singular) stays as the newest
                # one for pre-fill / backwards compat.
                quotes_list = []
                wc_payments = sorted(
                    (p for p in porder.payments.all() if p.provider == 'walletconnect'),
                    key=lambda p: p.created or porder.datetime,
                    reverse=True,
                )
                for p in wc_payments:
                    q = (p.info_data or {}).get('quote') or {}
                    if q and q.get('intended_payer'):
                        quotes_list.append({
                            'quoteId': q.get('quote_id'),
                            'chainId': q.get('chain_id'),
                            'symbol': q.get('symbol'),
                            'intendedPayer': q.get('intended_payer'),
                            'amountRaw': q.get('amount_raw'),
                            'createdAt': q.get('created_at'),
                            'expiresAt': q.get('expires_at'),
                        })
                quote_info = quotes_list[0] if quotes_list else None
                wc_unpaid.append({
                    'orderCode': porder.code,
                    'orderSecret': porder.secret,
                    'email': porder.email,
                    'total': str(porder.total),
                    'createdAt': int(porder.datetime.timestamp()) if porder.datetime else None,
                    'testmode': bool(porder.testmode),
                    'quote': quote_info,
                    'quotes': quotes_list,
                })
        except (ProgrammingError, Exception):
            log.exception('[admin_orders] wc_unpaid list failed; returning empty')

        agg = completed_qs.aggregate(total=Sum('total_usd'), count=Count('payment_reference'))
        total_usd = agg['total'] or Decimal('0')
        stats = {
            'pending': pending_qs.count(),
            'completed': len(completed),
            'x402Count': agg['count'] or 0,
            'legacyCount': len(legacy_wc),
            'wcUnpaidCount': len(wc_unpaid),
            'totalUsd': str(total_usd.quantize(Decimal('0.01'))),
        }

    return JsonResponse({
        'success': True,
        'stats': stats,
        'completed': completed,
        'pending': pending,
        'wcUnpaid': wc_unpaid,
    })


@csrf_exempt
@require_http_methods(['GET'])
@require_pretix_admin_token('can_view_orders')
def admin_stats(request: HttpRequest, **kwargs):
    org = request.GET.get('organizer', '')
    event_slug = request.GET.get('event', '')
    event = _get_event(org, event_slug)
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer

    from django.db.models import Sum, Count
    with scopes_disabled():
        pending_count = X402PendingOrder.objects.filter(event=event).count()
        stats = X402CompletedOrder.objects.filter(event=event).aggregate(
            completed_count=Count('payment_reference'),
            total=Sum('total_usd'),
        )
        completed_count = stats['completed_count'] or 0
        total = stats['total'] or Decimal('0')

    return JsonResponse({
        'success': True,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'total_usd': str(total.quantize(Decimal('0.01'))),
    })


@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_admin_token('can_change_orders')
def admin_refund(request: HttpRequest, **kwargs):
    action = request.GET.get('action', '')
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    forbidden = _check_event_access_or_403(request, event)
    if forbidden is not None:
        return forbidden

    payment_reference = body.get('payment_reference', '')
    if not payment_reference:
        return JsonResponse({'success': False, 'error': 'payment_reference required'}, status=400)

    if action == 'initiate':
        admin_address = body.get('admin_address', '')
        if not admin_address:
            return JsonResponse({'success': False, 'error': 'admin_address required'}, status=400)
        with scopes_disabled():
            ok = ticketstore.initiate_refund(
                event=event, payment_reference=payment_reference, admin_address=admin_address,
            )
        if not ok:
            return JsonResponse({'success': False, 'error': 'refund already pending or confirmed'}, status=409)
        return JsonResponse({'success': True})

    if action == 'confirm':
        tx_hash = body.get('refund_tx_hash', '')
        if not tx_hash:
            return JsonResponse({'success': False, 'error': 'refund_tx_hash required'}, status=400)
        with scopes_disabled():
            ok = ticketstore.finalize_refund(
                event=event, payment_reference=payment_reference, refund_tx_hash=tx_hash,
            )
            if not ok:
                return JsonResponse({'success': False, 'error': 'no pending refund to confirm'}, status=409)
            # Mirror the refund into Pretix so it shows up in the native admin.
            # Best-effort — failures are logged but don't undo the CAS above,
            # since the on-chain refund already happened and our bookkeeping
            # is correct; the Pretix side can always be reconciled later.
            completed = X402CompletedOrder.objects.filter(
                event=event, payment_reference=payment_reference,
            ).first()
            if completed and completed.pretix_order_code:
                from pretix_eth.x402.pretix_client import record_pretix_refund
                try:
                    record_pretix_refund(
                        event=event,
                        pretix_order_code=completed.pretix_order_code,
                        amount=completed.total_usd,
                        refund_tx_hash=tx_hash,
                        chain_id=completed.chain_id,
                    )
                except Exception as e:
                    log.warning(
                        '[x402 refund] failed to record Pretix OrderRefund for %s: %s',
                        payment_reference, e,
                    )
        return JsonResponse({'success': True})

    if action == 'fail':
        error = body.get('error', 'unknown')
        with scopes_disabled():
            ok = ticketstore.fail_refund(event=event, payment_reference=payment_reference, error=error)
        if not ok:
            return JsonResponse({'success': False, 'error': 'no pending refund to fail'}, status=409)
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': f'unknown action: {action}'}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_admin_token('can_change_orders')
def admin_wc_refund(request: HttpRequest, **kwargs):
    """Refund a legacy WalletConnect (pre-x402) order. Unlike the x402
    refund which keeps its own plugin-side CAS ledger on the
    `X402CompletedOrder` row, the WC path has no refund columns on
    `WCPaymentAttempt`. Bookkeeping lives entirely in Pretix's native
    `OrderRefund` — which IS the audit trail every operator expects to
    consult anyway.
    Idempotency: refuse to create a second OrderRefund for the same
    `refund_tx_hash` on the same order. The on-chain refund is
    already final; a double-record would just duplicate the Pretix-side
    audit line.
    """
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    forbidden = _check_event_access_or_403(request, event)
    if forbidden is not None:
        return forbidden

    pretix_order_code = body.get('pretix_order_code') or body.get('order_code') or ''
    refund_tx_hash = body.get('refund_tx_hash', '')
    chain_id = body.get('chain_id')
    amount = body.get('amount', '')
    if not pretix_order_code or not refund_tx_hash or chain_id is None or not amount:
        return JsonResponse({
            'success': False,
            'error': 'pretix_order_code, refund_tx_hash, chain_id, amount all required',
        }, status=400)
    try:
        chain_id_int = int(chain_id)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'invalid chain_id'}, status=400)

    import json as _json
    from django.db import transaction
    from pretix.base.models import Order
    # Atomic + select_for_update so two concurrent POSTs with the same
    # refund_tx_hash (admin double-click on a slow Confirm button) can't
    # both pass the idempotency check and both create OrderRefund rows.
    # Mirrors admin_wc_verify's lock pattern below.
    with scopes_disabled(), transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(event=event, code=pretix_order_code)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'pretix order not found'}, status=404)

        # Idempotency check: a refund with the same on-chain tx hash on
        # the same order is the same refund — return 409 so the admin UI
        # can show "already refunded" instead of re-creating.
        for r in order.refunds.all():
            try:
                existing_info = _json.loads(r.info or '{}')
            except (ValueError, TypeError):
                existing_info = {}
            if existing_info.get('refund_tx_hash') == refund_tx_hash:
                return JsonResponse({
                    'success': False,
                    'error': 'refund with this tx hash already recorded',
                    'refund_id': r.local_id,
                }, status=409)

        from pretix_eth.x402.pretix_client import record_pretix_refund
        try:
            refund = record_pretix_refund(
                event=event,
                pretix_order_code=pretix_order_code,
                amount=amount,
                refund_tx_hash=refund_tx_hash,
                chain_id=chain_id_int,
            )
        except Exception as e:
            log.exception('[wc refund] record_pretix_refund failed for %s', pretix_order_code)
            return JsonResponse({'success': False, 'error': f'pretix refund failed: {e}'}, status=500)

        if refund is None:
            return JsonResponse({
                'success': False,
                'error': 'could not record refund (no confirmed walletconnect payment on this order)',
            }, status=409)

        return JsonResponse({'success': True, 'refund_id': refund.local_id})


# ---------------------------------------------------------------------------
# Admin manual verification — operator-initiated recovery for payments
# where the buyer's auto-verify didn't complete (browser crash, RPC blip
# during the verify window, etc.). Re-runs the full verification pipeline
# against an existing X402PendingOrder. The pipeline enforces the same
# security controls as the user-facing endpoint (tx hash uniqueness, payer
# match, ETH signature, on-chain amount/recipient); only the IP-based rate
# limit is skipped (admin endpoint is auth-gated by Pretix API token).
# ---------------------------------------------------------------------------

_TX_HASH_RE = re.compile(r'^0x[a-fA-F0-9]{64}$')


@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_admin_token('can_change_orders')
def admin_verify(request: HttpRequest, **kwargs):
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    forbidden = _check_event_access_or_403(request, event)
    if forbidden is not None:
        return forbidden

    required = ('payment_reference', 'tx_hash', 'payer', 'chain_id', 'symbol')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({'success': False, 'error': f'missing fields: {missing}'}, status=400)

    tx_hash = body['tx_hash']
    if not _TX_HASH_RE.match(tx_hash):
        return JsonResponse({'success': False, 'error': 'invalid tx_hash format'}, status=400)
    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'invalid chain_id'}, status=400)

    with scopes_disabled():
        # Admin recovery: don't filter out expired pendings. The on-chain tx
        # is valid forever; the TTL is a UX guard for the buyer flow, not a
        # security control. Operators need to be able to verify a payment
        # whose user took >TTL to broadcast.
        pending = ticketstore.get_pending_order(
            event=event, payment_reference=body['payment_reference'],
            include_expired=True,
        )
    if pending is None:
        return JsonResponse({
            'success': False,
            'error': 'payment_reference not found (cannot verify against a missing pending order)',
        }, status=404)

    from pretix_eth.views_x402 import _x402_verify_and_finalize
    return _x402_verify_and_finalize(
        event=event, pending=pending,
        payment_reference=body['payment_reference'],
        tx_hash=tx_hash, chain_id=chain_id, symbol=body['symbol'],
        payer=body['payer'],
        # Admin recovery path: the user has typically already signed-and-sent,
        # then the verify call failed for some other reason (RPC flake, stale
        # bundle, browser closed before the receipt landed). Re-collecting a
        # fresh signature isn't practical, and on-chain verification still
        # binds payer→tx via `tx.from`, so the signature requirement is
        # bypassed here. The bypass is logged at WARNING for audit.
        eth_payer_signature=body.get('eth_payer_signature'),
        skip_eth_payer_signature=True,
    )


@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_admin_token('can_change_orders')
def admin_wc_verify(request: HttpRequest, **kwargs):
    """Admin manual verification for the legacy WC (wc_inject) flow — the
    counterpart of `admin_verify` for the x402 flow. Used when a buyer's
    auto-verify call didn't complete (closed browser, RPC blip, slow
    wallet broadcast) and the operator wants to confirm payment using a
    tx hash recovered out of band (block explorer, support ticket, etc.).

    Identifies the order by `order_code` rather than x402's
    `payment_reference` (wc_inject has no payment_reference — the buyer
    flow keys off the Pretix order + walletconnect OrderPayment in the
    `created` state).

    The admin chooses (chain_id, symbol, payer) — these may differ from
    the original quote stored on `payment.info_data` (e.g. buyer paid
    USDC on Base when their quote was for ETH on mainnet). The plugin
    computes the expected on-chain amount from `order.total` (USD) using
    the chosen symbol — for stables 1:1 USD, for ETH using the live dual-
    oracle price (NOT the quote-time price, since the admin is overriding
    the quote). On-chain verification then enforces recipient + amount
    + tx.from = payer + confirmations.

    Skipped vs the buyer flow:
      - The SIWE-lite signature (admin can't recover the in-session sig)
      - The IP rate limit (admin endpoint is token-auth-gated)
    Still enforced:
      - tx_hash uniqueness (no completed WCPaymentAttempt with this hash)
      - payer = the order quote's bound intended_payer (V68 — the admin cannot
        supply an arbitrary payer; the buyer address is fixed by the quote even
        when the admin overrides the symbol/chain the buyer actually paid on)
      - the quote freshness window on the settlement tx's block timestamp (V68 —
        a historical/unrelated transfer of the right amount is mined outside the
        window and rejected; the buyer's real payment is mined inside it)
      - payer = on-chain tx.from
      - amount = expected (per admin's chosen symbol + order.total)
      - recipient = provider.receive_address
      - min_confirmations
    """
    import asyncio
    from decimal import Decimal
    from django.db import IntegrityError, transaction
    from pretix.base.models import Order
    from pretix_eth.chains import is_supported, get_token_contract
    from pretix_eth.models import WCPaymentAttempt
    from pretix_eth.payment import WalletConnectPayment
    from pretix_eth.pricing import fetch_eth_price_usd, usd_to_token_raw
    from pretix_eth.verification import verify_erc20_transfer, verify_native_eth
    from pretix_eth.views import _get_web3, _wc_config_or_403

    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    forbidden = _check_event_access_or_403(request, event)
    if forbidden is not None:
        return forbidden

    required = ('order_code', 'order_secret', 'tx_hash', 'chain_id', 'symbol', 'payer')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({'success': False, 'error': f'missing fields: {missing}'}, status=400)

    tx_hash = body['tx_hash']
    if not _TX_HASH_RE.match(tx_hash):
        return JsonResponse({'success': False, 'error': 'invalid tx_hash format'}, status=400)
    tx_hash = tx_hash.lower()
    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'invalid chain_id'}, status=400)
    symbol = body['symbol']
    if not is_supported(chain_id, symbol):
        return JsonResponse({'success': False, 'error': 'unsupported chain/token combination'}, status=400)

    with scopes_disabled():
        # Constant-time secret compare, same as the buyer endpoint
        from hmac import compare_digest
        try:
            order = Order.objects.get(code=body['order_code'], event=event)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'order not found'}, status=404)
        if not compare_digest(order.secret, body['order_secret']):
            return JsonResponse({'success': False, 'error': 'order secret mismatch'}, status=403)

        payment = order.payments.filter(provider='walletconnect', state='created').first()
        if payment is None:
            return JsonResponse({
                'success': False,
                'error': 'no walletconnect payment in created state on this order',
            }, status=404)

        # V68: bind the manual verify to the buyer's OWN quote (its intended_payer).
        # Without a binding the endpoint would take `payer` from the request body
        # and match any on-chain transfer of the right amount to the shared
        # receive_address, letting an unrelated/historical transfer settle a fresh
        # order.
        #
        # Which quote? Buyers retry a lot — each retry spawns a fresh `created`
        # payment (usually quote-less) and they may switch wallet / token / chain
        # between attempts, so one order can carry SEVERAL quotes with different
        # payers and amounts. The admin picks the one matching the real on-chain
        # payment and passes its `quote_id`; we bind to THAT quote. With no
        # `quote_id` we fall back to the newest quote across all WC payments
        # (created + canceled) for direct API callers.
        force = _truthy(body.get('force') or body.get('override_no_quote'))
        quote_id = str(body.get('quote_id') or '').strip()
        if quote_id:
            quote = _find_wc_quote(order, quote_id)
            if not quote or not quote.get('intended_payer'):
                return JsonResponse({
                    'success': False, 'error': 'selected quote not found on this order',
                }, status=404)
        else:
            quote = _recover_wc_quote(order)

        if quote and quote.get('intended_payer'):
            if (body['payer'] or '').lower() != (quote['intended_payer'] or '').lower():
                return JsonResponse({
                    'success': False, 'error': 'payer does not match the selected quote',
                }, status=400)
            payer = quote['intended_payer']  # source of truth, not the request body
        elif force:
            # No quote on ANY of the order's payments (buyer never completed a
            # server-side quote). Fall back to the admin-supplied payer — the
            # pre-V68 rescue path, now GATED behind an explicit `force` flag and
            # loudly logged. The exact tx_hash, the full on-chain verification
            # (from == payer, to == receive_address, amount, confirmations) and
            # the one-time tx_hash dedup below all still apply, so `force` can only
            # settle a real, unused transfer from the stated payer to us.
            payer = body['payer']
            log.warning(
                '[wc admin verify] FORCE (no quote on order) order=%s tx=%s payer=%s (auth: admin token)',
                order.code, tx_hash, payer,
            )
        else:
            return JsonResponse({
                'success': False,
                'error': ('no quote/intended_payer on this order; pass force=true to verify '
                          'against the supplied payer (tx hash, on-chain payer/amount/recipient/'
                          'confirmations and one-time dedup are still enforced)'),
            }, status=409)

        # V46 parity: re-check WC enabled + per-chain + per-token toggles
        _, err = _wc_config_or_403(event, chain_id=chain_id, symbol=symbol)
        if err is not None:
            return err

        # Fail fast on one-time tx_hash check
        if WCPaymentAttempt.objects.filter(tx_hash=tx_hash, state='completed').exists():
            return JsonResponse({
                'success': False, 'error': 'tx already used for a completed order',
            }, status=409)

        # Expected on-chain amount. When the admin verifies against a real quote
        # on the SAME symbol + chain the buyer was quoted on, use that quote's
        # exact `amount_raw` — it's what the buyer was quoted and actually sent, so
        # this avoids ETH-price drift between payment time and rescue time (a live
        # recompute of order.total would no longer equal the sent amount and the
        # on-chain check would spuriously fail). Only recompute from order.total at
        # the LIVE price when there's no matching quote (force) or the admin is
        # deliberately overriding the quote's symbol/chain.
        quote_matches_request = bool(
            quote
            and str(quote.get('symbol')) == symbol
            and str(quote.get('chain_id')) == str(chain_id)
            and quote.get('amount_raw')
        )
        try:
            if quote_matches_request:
                amount_raw = int(quote['amount_raw'])
            elif symbol == 'ETH':
                price_result = asyncio.run(fetch_eth_price_usd())
                if price_result is None:
                    return JsonResponse({
                        'success': False, 'error': 'ETH oracle unavailable; retry later',
                    }, status=503)
                amount_raw = usd_to_token_raw(
                    Decimal(str(order.total)), 'ETH', chain_id, price_result.price,
                )
            else:
                amount_raw = usd_to_token_raw(
                    Decimal(str(order.total)), symbol, chain_id, eth_price=None,
                )
        except Exception as e:
            log.exception('[wc admin verify] amount computation failed for %s', order.code)
            return JsonResponse({'success': False, 'error': f'amount computation failed: {e}'}, status=500)

        provider = WalletConnectPayment(event)
        receive_address = provider.settings.get('receive_address')
        if not receive_address:
            return JsonResponse({'success': False, 'error': 'receive_address not configured'}, status=500)
        alchemy_key = provider.settings.get('alchemy_api_key', default=None)
        min_conf = int(provider.settings.get('min_confirmations', default=1))
        w3 = _get_web3(chain_id, alchemy_key)

        if symbol == 'ETH':
            vr = verify_native_eth(
                w3=w3, tx_hash=tx_hash,
                expected_from=payer,
                expected_to=receive_address,
                expected_amount_wei=amount_raw,
                min_confirmations=min_conf,
            )
        else:
            token_contract = get_token_contract(chain_id, symbol)
            if token_contract is None:
                return JsonResponse({'success': False, 'error': f'no contract for {symbol} on chain {chain_id}'}, status=400)
            vr = verify_erc20_transfer(
                w3=w3, chain_id=chain_id, tx_hash=tx_hash,
                expected_from=payer,
                expected_to=receive_address,
                expected_token=token_contract['address'],
                expected_amount=amount_raw,
                min_confirmations=min_conf,
            )

        if not vr.verified:
            log.warning(
                '[wc admin verify] on-chain verify failed order=%s tx=%s err=%s',
                order.code, tx_hash, vr.error,
            )
            return JsonResponse({
                'success': False,
                'error': vr.error,
                'confirmations': vr.confirmations,
                'confirmations_required': vr.min_confirmations,
            }, status=400)

        # V68: re-impose the quote freshness window on the settlement tx. A
        # historical/unrelated transfer of the right amount is mined outside the
        # window, so this rejects the replay the manual-verify tool otherwise
        # allowed. The buyer flow enforces the same window (V49); parity.
        #
        # Explicit admin override: a multi-owner Safe can take hours to collect
        # signatures, so its payment can legitimately mine AFTER the quote's
        # short TTL. `override_quote_window=true` lets the admin recover such a
        # payment. It skips ONLY the timestamp window; the payer<->quote binding
        # (above), the on-chain verification, and the one-time tx_hash dedup all
        # still apply, so it cannot settle an already-used or wrong-payer
        # transfer. The override is loudly logged + flagged on the payment for
        # audit, and is admin-token gated like the rest of this endpoint.
        # Skip the window when the admin explicitly overrides it, when we're on the
        # no-quote `force` path (no window to compare), or when the recovered quote
        # carries no timestamps.
        override_window = _truthy(body.get('override_quote_window')) or force or not quote
        try:
            block_ts = int(w3.eth.get_block(vr.block_number).timestamp)
        except Exception as e:
            return JsonResponse({
                'success': False, 'error': f'failed to fetch block timestamp: {e}',
            }, status=400)
        quote_created = int((quote or {}).get('created_at', 0))
        quote_expires = int((quote or {}).get('expires_at', 0))
        if override_window:
            log.warning(
                '[wc admin verify] OUT-OF-WINDOW OVERRIDE order=%s tx=%s block_ts=%s '
                'quote_window=[%s,%s] payer=%s force=%s (auth: admin token)',
                order.code, tx_hash, block_ts, quote_created, quote_expires, payer, force,
            )
        else:
            if quote_created and block_ts < quote_created:
                return JsonResponse({
                    'success': False, 'error': 'tx mined before quote was issued',
                }, status=400)
            if quote_expires and block_ts > quote_expires:
                return JsonResponse({
                    'success': False,
                    'error': ('tx mined after quote expired; set override_quote_window=true '
                              'to recover a legitimately-slow payment (e.g. Safe multisig)'),
                }, status=400)

        log.warning(
            '[wc admin verify] BYPASS — buyer signature skipped for order=%s tx=%s (auth: admin token)',
            order.code, tx_hash,
        )

        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order.pk)
                if order.status != Order.STATUS_PENDING:
                    return JsonResponse({
                        'success': False, 'error': f'order is not in pending state (status={order.status})',
                    }, status=410)

                WCPaymentAttempt.objects.create(
                    tx_hash=tx_hash,
                    # Prefer the recovered quote's id (the current `created` payment
                    # is often a quote-less retry); fall back to an admin marker.
                    quote_id=(quote or {}).get('quote_id') or f'admin_{tx_hash[:16]}',
                    order_code=order.code, payer=payer,
                    chain_id=chain_id, state='completed',
                )

                info = payment.info_data or {}
                info['tx_hash'] = tx_hash
                info['chain_id'] = chain_id
                info['token_symbol'] = symbol
                token_contract = get_token_contract(chain_id, symbol)
                info['token_address'] = token_contract['address'] if token_contract else None
                info['payer'] = payer
                info['amount'] = str(amount_raw)
                info['block_number'] = vr.block_number
                info['admin_manual_verify'] = True
                if override_window:
                    info['admin_out_of_window_override'] = True
                payment.info_data = info
                payment.save()

                try:
                    mail_text = provider.order_pending_mail_render(order, payment)
                except Exception as e:
                    log.warning('[wc admin verify] failed to render mail_text for %s: %s', order.code, e)
                    mail_text = ''
                payment.confirm(mail_text=mail_text)
        except IntegrityError:
            return JsonResponse({'success': False, 'error': 'tx already used (race)'}, status=409)

    return JsonResponse({
        'success': True,
        'order': {'code': order.code, 'secret': order.secret},
        'block_number': vr.block_number,
    })
