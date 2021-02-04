import pytest

from pretix.base.models import (
    OrderRefund,
    OrderPayment,
)

from pretix_eth.models import WalletAddress
from django.urls import reverse


@pytest.mark.django_db
def test_refund_created(event, organizer, create_admin_client, get_organizer_scope,
                        get_order_and_payment):
    assert not OrderRefund.objects.exists()

    order, payment = get_order_and_payment(
        payment_kwargs={'state': OrderPayment.PAYMENT_STATE_CONFIRMED, 'provider': 'ethereum'},
        info_data={'amount': '100', 'currency_type': 'ETH'}
    )

    WalletAddress.objects.create(event=event,
                                 hex_address='0x0000000000000000000000000000000000000001')
    WalletAddress.objects.get_for_order_payment(payment)

    url = reverse('control:event.order.refunds.start', kwargs={
        'event': event.slug,
        'organizer': organizer.slug,
        'code': order.code
    })

    client = create_admin_client(event)
    response = client.post(url, {
        f'refund-{payment.id}': '100',
        'start-mode': 'full',
        'perform': True
    })

    assert response.status_code == 302

    with get_organizer_scope():
        assert OrderRefund.objects.exists()
        assert OrderRefund.objects.count() == 1
        refund = OrderRefund.objects.first()
        assert refund.payment == payment
        assert refund.state == OrderRefund.REFUND_STATE_CREATED
        assert refund.info_data == {
            'currency_type': 'ETH',
            'amount': '100',
            'wallet_address': '0x0000000000000000000000000000000000000001',
        }


@pytest.mark.django_db
def test_invalid_refund_no_wallet(event, organizer, create_admin_client, get_order_and_payment):
    assert not OrderRefund.objects.exists()

    order, payment = get_order_and_payment(
        payment_kwargs={'state': OrderPayment.PAYMENT_STATE_CONFIRMED, 'provider': 'ethereum'},
        info_data={'amount': '100', 'currency_type': 'ETH'}
    )

    url = reverse('control:event.order.refunds.start', kwargs={
        'event': event.slug,
        'organizer': organizer.slug,
        'code': order.code
    })

    client = create_admin_client(event)

    with pytest.raises(ValueError, match='There is not assigned wallet address to this payment'):
        client.post(url, {
            f'refund-{payment.id}': '100',
            'start-mode': 'full',
            'perform': True
        })
