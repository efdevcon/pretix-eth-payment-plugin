from decimal import Decimal
from datetime import timedelta

import pytest
from django.utils import timezone
from django_scopes import scopes_disabled

from pretix_eth.models import X402PendingOrder, X402CompletedOrder, X402VerifyAttempt
from pretix_eth.x402.ticketstore import (
    store_pending_order, get_pending_order, claim_pending_order, cleanup_expired_pending,
    reserve_completed_order, finalize_completed_order, get_completed_by_tx_hash,
    TxHashAlreadyUsedError,
    initiate_refund, finalize_refund, fail_refund,
    check_verify_rate_limit, check_purchase_rate_limit, cleanup_verify_attempts,
)


# ---------------------------------------------------------------------------
# Task 13: Pending order CRUD
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_store_and_get_pending(event):
    with scopes_disabled():
        store_pending_order(
            event=event,
            payment_reference='x402_test1',
            order_data={'foo': 'bar'},
            total_usd=Decimal('50.00'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )
        got = get_pending_order(event=event, payment_reference='x402_test1')
        assert got is not None
        assert got.order_data == {'foo': 'bar'}


@pytest.mark.django_db
def test_get_expired_returns_none_by_default_but_keeps_row(event):
    """Expired pendings are hidden from the buyer flow but the row is kept
    so admin recovery (`include_expired=True`) can still resurrect it.
    Actual cleanup is the periodic task's job, not the read path's."""
    with scopes_disabled():
        past = timezone.now() - timedelta(seconds=1)
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_exp',
            order_data={}, total_usd=Decimal('1'), expires_at=past,
            intended_payer='0x' + '1' * 40,
        )
        got = get_pending_order(event=event, payment_reference='x402_exp')
        assert got is None
        # Row must still exist — cleanup is the periodic task's responsibility.
        assert X402PendingOrder.objects.filter(payment_reference='x402_exp').exists()


@pytest.mark.django_db
def test_get_expired_with_include_expired_returns_row(event):
    """Admin manual-verify path: expired pendings are still recoverable."""
    with scopes_disabled():
        past = timezone.now() - timedelta(seconds=1)
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_exp_admin',
            order_data={'foo': 'bar'}, total_usd=Decimal('1'), expires_at=past,
            intended_payer='0x' + '1' * 40,
        )
        got = get_pending_order(
            event=event, payment_reference='x402_exp_admin', include_expired=True,
        )
        assert got is not None
        assert got.order_data == {'foo': 'bar'}


@pytest.mark.django_db
def test_claim_atomically_deletes(event):
    with scopes_disabled():
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_claim',
            order_data={}, total_usd=Decimal('1'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )
        claimed = claim_pending_order(event=event, payment_reference='x402_claim')
        assert claimed is not None
        # Second claim must return None
        claimed2 = claim_pending_order(event=event, payment_reference='x402_claim')
        assert claimed2 is None


@pytest.mark.django_db
def test_cleanup_expired(event):
    with scopes_disabled():
        past = timezone.now() - timedelta(seconds=1)
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_old',
            order_data={}, total_usd=Decimal('1'), expires_at=past,
            intended_payer='0x' + '1' * 40,
        )
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_new',
            order_data={}, total_usd=Decimal('1'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '2' * 40,
        )
        n = cleanup_expired_pending()
        assert n == 1
        assert X402PendingOrder.objects.filter(payment_reference='x402_new').exists()
        assert not X402PendingOrder.objects.filter(payment_reference='x402_old').exists()


# ---------------------------------------------------------------------------
# Task 14: Completed order reserve/finalize
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_reserve_then_finalize(event):
    with scopes_disabled():
        reserved = reserve_completed_order(
            event=event, tx_hash='0x' + 'f' * 64,
            payment_reference='x402_r1', payer='0x' + '1' * 40,
            chain_id=8453, total_usd=Decimal('10'),
            token_symbol='USDC', crypto_amount='10.00',
        )
        assert reserved.pretix_order_code == '__RESERVED__'
        finalize_completed_order(event=event, payment_reference='x402_r1', pretix_order_code='REAL1')
        assert X402CompletedOrder.objects.get(payment_reference='x402_r1').pretix_order_code == 'REAL1'


@pytest.mark.django_db
def test_reserve_rejects_duplicate_tx_hash(event):
    with scopes_disabled():
        reserve_completed_order(
            event=event, tx_hash='0x' + 'd' * 64, payment_reference='x402_d1',
            payer='0x' + '1' * 40, chain_id=8453, total_usd=Decimal('10'),
            token_symbol='USDC',
        )
        with pytest.raises(TxHashAlreadyUsedError):
            reserve_completed_order(
                event=event, tx_hash='0x' + 'd' * 64,  # duplicate
                payment_reference='x402_d2',
                payer='0x' + '2' * 40, chain_id=10, total_usd=Decimal('20'),
                token_symbol='USDC',
            )


@pytest.mark.django_db
def test_lookup_by_tx_hash(event):
    with scopes_disabled():
        reserve_completed_order(
            event=event, tx_hash='0x' + 'e' * 64, payment_reference='x402_e1',
            payer='0x' + '1' * 40, chain_id=8453, total_usd=Decimal('10'),
            token_symbol='USDC',
        )
        finalize_completed_order(event=event, payment_reference='x402_e1', pretix_order_code='E1')
        got = get_completed_by_tx_hash('0x' + 'e' * 64)
        assert got is not None
        assert got.pretix_order_code == 'E1'


# ---------------------------------------------------------------------------
# Task 15: Refund state machine
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_initiate_refund_cas(event):
    with scopes_disabled():
        reserve_completed_order(
            event=event, tx_hash='0x' + 'a' * 64, payment_reference='x402_ref1',
            payer='0x' + '1' * 40, chain_id=8453, total_usd=Decimal('10'),
            token_symbol='USDC',
        )
        finalize_completed_order(event=event, payment_reference='x402_ref1', pretix_order_code='R1')

        ok = initiate_refund(event=event, payment_reference='x402_ref1', admin_address='0x' + '9' * 40)
        assert ok is True
        o = X402CompletedOrder.objects.get(payment_reference='x402_ref1')
        assert o.refund_status == 'pending'

        # Second initiate should fail (already pending)
        ok2 = initiate_refund(event=event, payment_reference='x402_ref1', admin_address='0x' + '9' * 40)
        assert ok2 is False


@pytest.mark.django_db
def test_initiate_refund_retries_failed(event):
    with scopes_disabled():
        reserve_completed_order(
            event=event, tx_hash='0x' + 'b' * 64, payment_reference='x402_ref2',
            payer='0x' + '1' * 40, chain_id=8453, total_usd=Decimal('10'),
            token_symbol='USDC',
        )
        finalize_completed_order(event=event, payment_reference='x402_ref2', pretix_order_code='R2')
        fail_refund(event=event, payment_reference='x402_ref2', error='network error')
        # Should be able to re-initiate after a failure
        ok = initiate_refund(event=event, payment_reference='x402_ref2', admin_address='0x' + '9' * 40)
        assert ok is True


@pytest.mark.django_db
def test_finalize_refund(event):
    with scopes_disabled():
        reserve_completed_order(
            event=event, tx_hash='0x' + 'c' * 64, payment_reference='x402_ref3',
            payer='0x' + '1' * 40, chain_id=8453, total_usd=Decimal('10'),
            token_symbol='USDC',
        )
        finalize_completed_order(event=event, payment_reference='x402_ref3', pretix_order_code='R3')
        initiate_refund(event=event, payment_reference='x402_ref3', admin_address='0x' + '9' * 40)
        finalize_refund(event=event, payment_reference='x402_ref3', refund_tx_hash='0x' + 'd' * 64)
        o = X402CompletedOrder.objects.get(payment_reference='x402_ref3')
        assert o.refund_status == 'confirmed'
        assert o.refund_tx_hash == '0x' + 'd' * 64
        assert 'refundedAt' in o.refund_meta


# ---------------------------------------------------------------------------
# Task 16: Rate limiting
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_verify_rate_limit_enforced():
    # Per-ref limit: 10/hour, no 2 within 10s
    for _ in range(10):
        allowed = check_verify_rate_limit(payment_reference='refA', client_ip='1.2.3.4')
        assert allowed
    # 11th should be blocked
    assert check_verify_rate_limit(payment_reference='refA', client_ip='1.2.3.4') is False


@pytest.mark.django_db
def test_verify_rate_limit_independent_per_ref():
    for _ in range(10):
        assert check_verify_rate_limit(payment_reference='refB', client_ip='1.2.3.4')
    assert check_verify_rate_limit(payment_reference='refC', client_ip='1.2.3.4')


@pytest.mark.django_db
def test_purchase_rate_limit():
    for _ in range(5):
        assert check_purchase_rate_limit(client_ip='2.3.4.5')
    assert check_purchase_rate_limit(client_ip='2.3.4.5') is False


@pytest.mark.django_db
def test_cleanup_verify_attempts():
    old_time = timezone.now() - timedelta(hours=3)
    a = X402VerifyAttempt.objects.create(key='verify_ref:old')
    X402VerifyAttempt.objects.filter(pk=a.pk).update(created_at=old_time)
    X402VerifyAttempt.objects.create(key='verify_ref:new')
    n = cleanup_verify_attempts()
    assert n == 1
    assert X402VerifyAttempt.objects.filter(key='verify_ref:new').exists()
    assert not X402VerifyAttempt.objects.filter(key='verify_ref:old').exists()
