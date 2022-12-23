import pytest
from django.urls import reverse

from pretix.base.models import OrderPayment


@pytest.mark.django_db
def test_headers_are_present(organizer, event, create_admin_client):
    expected_headers = [
        'Type',
        'Event slug',
        'Order',
        'Payment ID',
        'Creation date',
        'Completion date',
        'Status',
        'Fiat Amount',
        'Token Amount',
        'Token',
        'ETH or DAI sender address',
        'ETH or DAI receiver address',
        'Transaction Hash',
        'Chain ID',
        'DAI contract address',
    ]

    admin_clinet = create_admin_client(event)

    url = reverse(
        "control:event.orders.export.do",
        kwargs={"event": event.slug, "organizer": organizer.slug},
    )

    response = admin_clinet.post(
        url, {"exporter": "ethorders", "ethorders-_format": "default"}, follow=True
    )

    assert response.status_code == 200

    file_content = "".join(str(row) for row in response.streaming_content)

    for header in expected_headers:
        assert header in file_content


@pytest.fixture
def create_payment_with_address(get_order_and_payment, event, provider):
    def _create_payment_with_address(
        payment_kwargs={
            "state": OrderPayment.PAYMENT_STATE_CONFIRMED,
            "amount": "100",
            "provider": "ethereum",
        },
        info_data={"currency_type": "ETH - L1", "amount": "100"},
    ):

        _, payment = get_order_and_payment(
            payment_kwargs=payment_kwargs, info_data=info_data
        )

        return payment

    return _create_payment_with_address


@pytest.mark.django_db
def test_payment_data_present(
    organizer, event, create_admin_client, create_payment_with_address
):
    assert not OrderPayment.objects.exists()

    create_payment_with_address()

    assert OrderPayment.objects.exists()

    admin_clinet = create_admin_client(event)

    url = reverse(
        "control:event.orders.export.do",
        kwargs={"event": event.slug, "organizer": organizer.slug},
    )

    response = admin_clinet.post(
        url,
        {
            "exporter": "ethorders",
            "ethorders-_format": "default",
            "ethorders-payment_states": "confirmed",
        },
        follow=True,
    )

    assert response.status_code == 200

    assert response.streaming is True
    file_content = "".join(str(row) for row in response.streaming_content)

    assert "ETH - L1" in file_content
    assert "Payment" in file_content
    assert "100.0" in file_content
