import pytest
from django.db import IntegrityError
from pretix_eth.models import WCPaymentAttempt


@pytest.mark.django_db
def test_tx_hash_unique():
    WCPaymentAttempt.objects.create(
        tx_hash='0x' + 'a' * 64, quote_id='q1', order_code='ABCDE',
        payer='0x' + 'b' * 40, chain_id=8453, state='completed',
    )
    with pytest.raises(IntegrityError):
        WCPaymentAttempt.objects.create(
            tx_hash='0x' + 'a' * 64, quote_id='q2', order_code='FGHIJ',
            payer='0x' + 'c' * 40, chain_id=10, state='claiming',
        )


@pytest.mark.django_db
def test_can_create_and_read():
    WCPaymentAttempt.objects.create(
        tx_hash='0x' + 'c' * 64, quote_id='qx', order_code='XXX',
        payer='0x' + 'b' * 40, chain_id=8453, state='claiming',
    )
    assert WCPaymentAttempt.objects.filter(tx_hash='0x' + 'c' * 64).exists()
