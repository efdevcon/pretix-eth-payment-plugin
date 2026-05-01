# tests/core/test_x402_models.py
import pytest
from decimal import Decimal
from django.utils import timezone
from django_scopes import scopes_disabled
from pretix_eth.models import X402PendingOrder, X402CompletedOrder, X402VerifyAttempt


@pytest.mark.django_db
def test_pending_order_create_and_read(event):
    with scopes_disabled():
        X402PendingOrder.objects.create(
            event=event,
            payment_reference='x402_abc',
            order_data={'email': 'a@b.c', 'tickets': []},
            total_usd=Decimal('50.00'),
            expires_at=timezone.now(),
            intended_payer='0x' + '1' * 40,
        )
        got = X402PendingOrder.objects.get(payment_reference='x402_abc')
        assert got.order_data['email'] == 'a@b.c'
        assert got.total_usd == Decimal('50.00')
        assert got.intended_payer == '0x' + '1' * 40


@pytest.mark.django_db
def test_completed_order_unique_tx_hash(event):
    from django.db import IntegrityError
    with scopes_disabled():
        X402CompletedOrder.objects.create(
            event=event,
            payment_reference='x402_one',
            tx_hash='0x' + 'a' * 64,
            pretix_order_code='ABCDE',
            payer='0x' + '1' * 40,
            chain_id=8453,
            total_usd=Decimal('50.00'),
            token_symbol='USDC',
        )
        with pytest.raises(IntegrityError):
            X402CompletedOrder.objects.create(
                event=event,
                payment_reference='x402_two',
                tx_hash='0x' + 'a' * 64,  # duplicate
                pretix_order_code='FGHIJ',
                payer='0x' + '2' * 40,
                chain_id=10,
                total_usd=Decimal('50.00'),
                token_symbol='USDC',
            )


@pytest.mark.django_db
def test_completed_order_refund_fields(event):
    with scopes_disabled():
        o = X402CompletedOrder.objects.create(
            event=event,
            payment_reference='x402_r',
            tx_hash='0x' + 'b' * 64,
            pretix_order_code='XXXXX',
            payer='0x' + '3' * 40,
            chain_id=8453,
            total_usd=Decimal('25.00'),
            token_symbol='USDC',
        )
        assert o.refund_status is None
        assert o.refund_meta == {}


@pytest.mark.django_db
def test_verify_attempt_create(event):
    with scopes_disabled():
        X402VerifyAttempt.objects.create(key='verify_ref:abc')
        X402VerifyAttempt.objects.create(key='verify_ip:1.2.3.4')
        assert X402VerifyAttempt.objects.count() == 2
