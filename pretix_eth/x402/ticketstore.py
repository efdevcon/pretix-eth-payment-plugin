"""Django ORM wrapper mirroring devcon's services/ticketStore.ts.

Concurrency: claim_pending_order and reserve_completed_order both use
atomic operations (DELETE ... RETURNING for claim; INSERT with unique constraint
for reserve). Race conditions are resolved at the database level.
"""
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone

from pretix_eth.models import X402PendingOrder, X402CompletedOrder, X402VerifyAttempt


# ---------------------------------------------------------------------------
# Pending order CRUD (Task 13)
# ---------------------------------------------------------------------------

def store_pending_order(
    *,
    event,
    payment_reference: str,
    order_data: dict,
    total_usd: Decimal,
    expires_at: datetime,
    intended_payer: str,
    expected_eth_amount_wei_by_chain: Optional[dict] = None,
    expected_chain_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> X402PendingOrder:
    return X402PendingOrder.objects.create(
        event=event,
        payment_reference=payment_reference,
        order_data=order_data,
        total_usd=total_usd,
        expires_at=expires_at,
        intended_payer=intended_payer,
        expected_eth_amount_wei_by_chain=expected_eth_amount_wei_by_chain,
        expected_chain_id=expected_chain_id,
        metadata=metadata,
    )


def get_pending_order(
    *, event, payment_reference: str, include_expired: bool = False,
) -> Optional[X402PendingOrder]:
    """Returns the pending order if it exists.

    Default behaviour (used by the buyer-facing verify endpoint): treat an
    expired row as if it doesn't exist — the buyer needs to refresh quote.

    Pass `include_expired=True` from operator-only paths (admin manual
    verify) to recover stuck payments whose pending row has aged past its
    TTL. The on-chain tx is valid forever, so the plugin should still be
    able to bind it to the order.

    Notably this does NOT delete expired rows as a side effect anymore —
    that previously made admin recovery impossible if any buyer-side call
    happened to hit `verify` first. Actual cleanup is handled hourly by
    `cleanup_expired_pending_task` (registered via Pretix's `periodic_task`
    signal in `signals.py`), which gives operators up to ~1 h to recover
    a stuck payment after its quote TTL elapses.
    """
    try:
        o = X402PendingOrder.objects.get(event=event, payment_reference=payment_reference)
    except X402PendingOrder.DoesNotExist:
        return None
    if o.expires_at < timezone.now() and not include_expired:
        return None
    return o


def claim_pending_order(*, event, payment_reference: str) -> Optional[X402PendingOrder]:
    """Atomically delete-and-return the pending order. Guarantees one-time use:
    if two concurrent verifies race, only one gets the row back."""
    with transaction.atomic():
        try:
            o = X402PendingOrder.objects.select_for_update().get(
                event=event, payment_reference=payment_reference,
            )
        except X402PendingOrder.DoesNotExist:
            return None
        # Capture data before delete
        data = X402PendingOrder(
            event=o.event, payment_reference=o.payment_reference,
            order_data=o.order_data, total_usd=o.total_usd,
            expires_at=o.expires_at, intended_payer=o.intended_payer,
            expected_eth_amount_wei_by_chain=o.expected_eth_amount_wei_by_chain,
            expected_chain_id=o.expected_chain_id, metadata=o.metadata,
        )
        o.delete()
        return data


def cleanup_expired_pending() -> int:
    """Delete all pending orders past their expires_at. Returns count deleted."""
    n, _ = X402PendingOrder.objects.filter(expires_at__lt=timezone.now()).delete()
    return n


# ---------------------------------------------------------------------------
# Completed order reserve/finalize (Task 14)
# ---------------------------------------------------------------------------

class TxHashAlreadyUsedError(Exception):
    pass


def reserve_completed_order(
    *,
    event,
    tx_hash: str,
    payment_reference: str,
    payer: str,
    chain_id: int,
    total_usd: Decimal,
    token_symbol: str,
    crypto_amount: Optional[str] = None,
    gas_cost_wei: Optional[str] = None,
) -> X402CompletedOrder:
    """Insert a completed order with placeholder pretix_order_code.
    Raises TxHashAlreadyUsedError if another order already claimed this tx hash
    (unique constraint). Must be called BEFORE creating the Pretix order."""
    try:
        return X402CompletedOrder.objects.create(
            event=event, tx_hash=tx_hash, payment_reference=payment_reference,
            pretix_order_code='__RESERVED__', payer=payer, chain_id=chain_id,
            total_usd=total_usd, token_symbol=token_symbol,
            crypto_amount=crypto_amount, gas_cost_wei=gas_cost_wei,
        )
    except IntegrityError as e:
        raise TxHashAlreadyUsedError(f'tx_hash {tx_hash} already used') from e


def finalize_completed_order(*, event, payment_reference: str, pretix_order_code: str) -> None:
    X402CompletedOrder.objects.filter(
        event=event, payment_reference=payment_reference,
    ).update(pretix_order_code=pretix_order_code)


def remove_completed_reservation(*, event, payment_reference: str) -> None:
    """Rollback: called when the Pretix order creation fails after reserve."""
    X402CompletedOrder.objects.filter(
        event=event, payment_reference=payment_reference,
        pretix_order_code='__RESERVED__',
    ).delete()


def get_completed_by_tx_hash(tx_hash: str) -> Optional[X402CompletedOrder]:
    try:
        return X402CompletedOrder.objects.get(tx_hash=tx_hash)
    except X402CompletedOrder.DoesNotExist:
        return None


def get_completed_by_payment_ref(
    *, event, payment_reference: str,
) -> Optional[X402CompletedOrder]:
    try:
        return X402CompletedOrder.objects.get(event=event, payment_reference=payment_reference)
    except X402CompletedOrder.DoesNotExist:
        return None


# ---------------------------------------------------------------------------
# Refund state machine (Task 15)
# ---------------------------------------------------------------------------

def initiate_refund(*, event, payment_reference: str, admin_address: str) -> bool:
    """CAS: NULL -> 'pending' or 'failed' -> 'pending'. Returns True on success,
    False if refund is already pending or confirmed."""
    now_iso = timezone.now().isoformat()
    # Step 1: Try NULL -> pending
    updated = X402CompletedOrder.objects.filter(
        event=event, payment_reference=payment_reference, refund_status__isnull=True,
    ).update(
        refund_status=X402CompletedOrder.REFUND_PENDING,
        refund_meta={'initiatedBy': admin_address, 'initiatedAt': now_iso},
    )
    if updated:
        return True
    # Step 2: Try 'failed' -> pending (retry after failure)
    updated = X402CompletedOrder.objects.filter(
        event=event, payment_reference=payment_reference,
        refund_status=X402CompletedOrder.REFUND_FAILED,
    ).update(
        refund_status=X402CompletedOrder.REFUND_PENDING,
        refund_meta={'initiatedBy': admin_address, 'initiatedAt': now_iso, 'retryAfterFailure': True},
    )
    return bool(updated)


def finalize_refund(*, event, payment_reference: str, refund_tx_hash: str) -> bool:
    """'pending' -> 'confirmed' with refund_tx_hash. Merges refundedAt into refund_meta."""
    with transaction.atomic():
        try:
            o = X402CompletedOrder.objects.select_for_update().get(
                event=event, payment_reference=payment_reference,
                refund_status=X402CompletedOrder.REFUND_PENDING,
            )
        except X402CompletedOrder.DoesNotExist:
            return False
        o.refund_status = X402CompletedOrder.REFUND_CONFIRMED
        o.refund_tx_hash = refund_tx_hash
        o.refund_meta = {**(o.refund_meta or {}), 'refundedAt': timezone.now().isoformat()}
        o.save()
        return True


def fail_refund(*, event, payment_reference: str, error: str) -> bool:
    """'pending' -> 'failed' with error message in refund_meta."""
    with transaction.atomic():
        try:
            o = X402CompletedOrder.objects.select_for_update().get(
                event=event, payment_reference=payment_reference,
                refund_status=X402CompletedOrder.REFUND_PENDING,
            )
        except X402CompletedOrder.DoesNotExist:
            return False
        o.refund_status = X402CompletedOrder.REFUND_FAILED
        o.refund_meta = {
            **(o.refund_meta or {}),
            'error': error,
            'failedAt': timezone.now().isoformat(),
        }
        o.save()
        return True


# ---------------------------------------------------------------------------
# Rate limiting (Task 16)
# ---------------------------------------------------------------------------

RATE_LIMIT_REF_WINDOW = timedelta(hours=1)
RATE_LIMIT_REF_MAX = 10
RATE_LIMIT_IP_WINDOW = timedelta(minutes=1)
RATE_LIMIT_IP_MAX = 30
RATE_LIMIT_PURCHASE_WINDOW = timedelta(minutes=1)
RATE_LIMIT_PURCHASE_MAX = 5
RATE_LIMIT_CLEANUP_AGE = timedelta(hours=2)


def check_verify_rate_limit(*, payment_reference: str, client_ip: str) -> bool:
    """Returns True if allowed, False if over limit. Records the attempt."""
    now = timezone.now()
    ref_since = now - RATE_LIMIT_REF_WINDOW
    ip_since = now - RATE_LIMIT_IP_WINDOW
    ref_key = f'verify_ref:{payment_reference}'
    ip_key = f'verify_ip:{client_ip}'

    ref_count = X402VerifyAttempt.objects.filter(key=ref_key, created_at__gte=ref_since).count()
    if ref_count >= RATE_LIMIT_REF_MAX:
        return False
    ip_count = X402VerifyAttempt.objects.filter(key=ip_key, created_at__gte=ip_since).count()
    if ip_count >= RATE_LIMIT_IP_MAX:
        return False

    X402VerifyAttempt.objects.bulk_create([
        X402VerifyAttempt(key=ref_key),
        X402VerifyAttempt(key=ip_key),
    ])
    return True


def check_purchase_rate_limit(*, client_ip: str) -> bool:
    """Returns True if allowed. Records the attempt."""
    now = timezone.now()
    since = now - RATE_LIMIT_PURCHASE_WINDOW
    key = f'purchase_ip:{client_ip}'
    count = X402VerifyAttempt.objects.filter(key=key, created_at__gte=since).count()
    if count >= RATE_LIMIT_PURCHASE_MAX:
        return False
    X402VerifyAttempt.objects.create(key=key)
    return True


def cleanup_verify_attempts() -> int:
    """Delete all verify attempts older than the cleanup age."""
    cutoff = timezone.now() - RATE_LIMIT_CLEANUP_AGE
    n, _ = X402VerifyAttempt.objects.filter(created_at__lt=cutoff).delete()
    return n
