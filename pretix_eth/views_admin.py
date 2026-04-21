"""x402 admin endpoints — orders list, stats, refund actions."""
import json
import logging
from decimal import Decimal

from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_scopes import scopes_disabled

from pretix_eth.models import X402CompletedOrder, X402PendingOrder
from pretix_eth.x402.auth import require_pretix_token
from pretix_eth.x402 import ticketstore

log = logging.getLogger(__name__)


_CAMEL_TO_SNAKE_ADMIN = {
    'paymentReference': 'payment_reference',
    'adminAddress': 'admin_address',
    'refundTxHash': 'refund_tx_hash',
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


def _serialize_completed(o: X402CompletedOrder) -> dict:
    return {
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
        'refundStatus': o.refund_status,
        'refundTxHash': o.refund_tx_hash,
        'refundMeta': o.refund_meta or {},
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
    with scopes_disabled():
        completed_qs = X402CompletedOrder.objects.filter(event=event)
        pending_qs = X402PendingOrder.objects.filter(event=event)
        completed = [_serialize_completed(o) for o in completed_qs.order_by('-completed_at')[:500]]
        pending = [_serialize_pending(o) for o in pending_qs.order_by('-created_at')[:200]]
        agg = completed_qs.aggregate(total=Sum('total_usd'), count=Count('payment_reference'))
        total_usd = agg['total'] or Decimal('0')
        stats = {
            'pending': pending_qs.count(),
            'completed': agg['count'] or 0,
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
        return JsonResponse({'success': True})

    if action == 'fail':
        error = body.get('error', 'unknown')
        with scopes_disabled():
            ok = ticketstore.fail_refund(event=event, payment_reference=payment_reference, error=error)
        if not ok:
            return JsonResponse({'success': False, 'error': 'no pending refund to fail'}, status=409)
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': f'unknown action: {action}'}, status=400)
