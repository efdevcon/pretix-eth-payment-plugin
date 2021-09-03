import pytest
from django.urls import reverse

from pretix.base.models import (
    OrderPayment,
    OrderRefund,
)

from pretix_eth.models import WalletAddress


@pytest.mark.django_db
def test_headers_are_present(organizer, event, create_admin_client):
    expected_headers = ['Type', 'Event slug', 'Order', 'Payment ID', 'Creation date',
                        'Completion date', 'Status', 'Amount', 'Token', 'Wallet address']

    admin_clinet = create_admin_client(event)

    url = reverse('control:event.orders.export.do', kwargs={
        'event': event.slug,
        'organizer': organizer.slug
    })

    response = admin_clinet.post(url, {
        'exporter': 'ethorders',
        'ethorders-_format': 'default'
    }, follow=True)

    assert response.status_code == 200

    file_content = ''.join(str(row) for row in response.streaming_content)

    for header in expected_headers:
        assert header in file_content


@pytest.fixture
def create_payment_with_address(get_order_and_payment, event, provider):
    def _create_payment_with_address(
            payment_kwargs={
                'state': OrderPayment.PAYMENT_STATE_CONFIRMED,
                'amount': '100.0',
                'provider': 'ethereum'
            },
            info_data={
                'currency_type': 'ETH - L1',
                'amount': '100.0'
            },
            hex_address='0x0000000000000000000000000000000000000000'):

        _, payment = get_order_and_payment(payment_kwargs=payment_kwargs, info_data=info_data)

        WalletAddress.objects.create(
            event=event,
            hex_address=hex_address
        )
        WalletAddress.objects.get_for_order_payment(payment)

        return payment
    return _create_payment_with_address


@pytest.mark.django_db
def test_payment_data_present(organizer, event, create_admin_client, create_payment_with_address):
    assert not OrderPayment.objects.exists()

    create_payment_with_address()

    assert OrderPayment.objects.exists()

    admin_clinet = create_admin_client(event)

    url = reverse('control:event.orders.export.do', kwargs={
        'event': event.slug,
        'organizer': organizer.slug
    })

    response = admin_clinet.post(url, {
        'exporter': 'ethorders',
        'ethorders-_format': 'default',
        'ethorders-payment_states': 'confirmed'
    }, follow=True)

    assert response.status_code == 200

    file_content = ''.join(str(row) for row in response.streaming_content)

    assert '0x0000000000000000000000000000000000000000' in file_content
    assert 'ETH - L1' in file_content
    assert 'Payment' in file_content
    assert '100.0' in file_content


@pytest.mark.django_db
def test_refund_data_present(organizer, event, create_admin_client,
                             create_payment_with_address, provider, get_organizer_scope):
    assert not OrderRefund.objects.exists()

    payment = create_payment_with_address()

    with get_organizer_scope():
        refund = payment.order.refunds.create(
            payment=payment,
            source=OrderRefund.REFUND_SOURCE_ADMIN,
            state=OrderRefund.REFUND_STATE_CREATED,
            amount=payment.amount,
            provider='ethereum'
        )
    provider.execute_refund(refund)

    assert OrderRefund.objects.exists()

    admin_clinet = create_admin_client(event)

    url = reverse('control:event.orders.export.do', kwargs={
        'event': event.slug,
        'organizer': organizer.slug
    })

    response = admin_clinet.post(url, {
        'exporter': 'ethorders',
        'ethorders-_format': 'default',
        'ethorders-refund_states': 'created'
    }, follow=True)

    assert response.status_code == 200

    file_content = ''.join(str(row) for row in response.streaming_content)

    assert 'Refund' in file_content
    assert 'ETH - L1' in file_content
    assert '0x0000000000000000000000000000000000000000' in file_content
    assert '100.0' in file_content
