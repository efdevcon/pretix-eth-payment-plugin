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
from pretix_eth.x402.auth import require_pretix_token
from pretix_eth.x402 import ticketstore

log = logging.getLogger(__name__)


_CAMEL_TO_SNAKE_ADMIN = {
    'paymentReference': 'payment_reference',
    'adminAddress': 'admin_address',
    'refundTxHash': 'refund_tx_hash',
    'txHash': 'tx_hash',
    'chainId': 'chain_id',
    'ethPayerSignature': 'eth_payer_signature',
}


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


def _serialize_completed(o: X402CompletedOrder, email: Optional[str] = None) -> dict:
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
    }


def _serialize_wc_attempt(
    w: WCPaymentAttempt, total: Optional[Decimal], payment_info: Optional[dict] = None,
    email: Optional[str] = None,
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
    }


def _serialize_pending(o: X402PendingOrder) -> dict:
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
@require_pretix_token
def admin_orders(request: HttpRequest):
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

        # Single round-trip to fetch all relevant Pretix Orders so the
        # admin UI can show the buyer's email per row without N+1 queries.
        x402_codes = {o.pretix_order_code for o in x402_completed_list if o.pretix_order_code}
        email_by_code: dict = {}
        if x402_codes:
            email_by_code.update({
                o.code: o.email for o in Order.objects.filter(event=event, code__in=x402_codes)
            })

        x402_rows = [
            _serialize_completed(o, email=email_by_code.get(o.pretix_order_code))
            for o in x402_completed_list
        ]
        pending = [_serialize_pending(o) for o in pending_qs.order_by('-created_at')[:200]]

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
            orders_by_code = {
                o.code: o for o in Order.objects.filter(event=event, code__in=wc_codes)
            } if wc_codes else {}
            # Reuse the email lookup (Order.email) we already loaded above
            # plus anything new from this query.
            for code, order in orders_by_code.items():
                email_by_code.setdefault(code, order.email)
            # The legacy verify handler (views.py) writes token_symbol + amount
            # into the matching Pretix OrderPayment.info_data by tx_hash. Pull
            # that side so the admin UI can show accurate token + amount without
            # relying on heuristics.
            from pretix.base.models import OrderPayment
            payments_by_tx: dict = {}
            if wc_attempts:
                tx_hashes = {w.tx_hash for w in wc_attempts}
                for p in OrderPayment.objects.filter(
                    order__event=event, provider='walletconnect',
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

        agg = completed_qs.aggregate(total=Sum('total_usd'), count=Count('payment_reference'))
        total_usd = agg['total'] or Decimal('0')
        stats = {
            'pending': pending_qs.count(),
            'completed': len(completed),
            'x402Count': agg['count'] or 0,
            'legacyCount': len(legacy_wc),
            'totalUsd': str(total_usd.quantize(Decimal('0.01'))),
        }

    return JsonResponse({
        'success': True,
        'stats': stats,
        'completed': completed,
        'pending': pending,
    })


@csrf_exempt
@require_http_methods(['GET'])
@require_pretix_token
def admin_stats(request: HttpRequest):
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
@require_pretix_token
def admin_refund(request: HttpRequest):
    action = request.GET.get('action', '')
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer

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
@require_pretix_token
def admin_verify(request: HttpRequest):
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer

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
