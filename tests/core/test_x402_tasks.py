import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django_scopes import scopes_disabled
from pretix_eth.models import X402PendingOrder, X402VerifyAttempt


@pytest.mark.django_db
def test_cleanup_expired_pending_task(event):
    with scopes_disabled():
        past = timezone.now() - timedelta(seconds=1)
        X402PendingOrder.objects.create(
            event=event, payment_reference='old', order_data={},
            total_usd=Decimal('1'), expires_at=past, intended_payer='0x' + '1' * 40,
        )
    from pretix_eth.x402.tasks import cleanup_expired_pending_task
    result = cleanup_expired_pending_task()
    assert result['deleted'] == 1


@pytest.mark.django_db
def test_cleanup_verify_attempts_task():
    old = timezone.now() - timedelta(hours=3)
    a = X402VerifyAttempt.objects.create(key='verify_ref:xy')
    X402VerifyAttempt.objects.filter(pk=a.pk).update(created_at=old)
    from pretix_eth.x402.tasks import cleanup_verify_attempts_task
    result = cleanup_verify_attempts_task()
    assert result['deleted'] == 1
