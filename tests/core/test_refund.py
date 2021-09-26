import pytest

from pretix.base.models import (
    OrderRefund,
    OrderPayment,
)

from pretix_eth.models import WalletAddress
from django.urls import reverse


def make_refund(client, event, order, payment, organizer):
    url = reverse(
        "control:event.order.refunds.start",
        kwargs={"event": event.slug, "organizer": organizer.slug, "code": order.code},
    )

    response = client.post(
        url, {f"refund-{payment.id}": "100", "start-mode": "full", "perform": True}
    )

    return response


@pytest.mark.django_db
def test_refund_created(
    event, organizer, create_admin_client, get_organizer_scope, get_order_and_payment
):
    assert not OrderRefund.objects.exists()

    order, payment = get_order_and_payment(
        payment_kwargs={
            "state": OrderPayment.PAYMENT_STATE_CONFIRMED,
            "provider": "ethereum",
        },
        info_data={"amount": "100", "currency_type": "ETH - L1"},
    )

    WalletAddress.objects.create(
        event=event, hex_address="0x0000000000000000000000000000000000000001"
    )
    WalletAddress.objects.get_for_order_payment(payment)

    client = create_admin_client(event)
    response = make_refund(client, event, order, payment, organizer)

    assert response.status_code == 302

    with get_organizer_scope():
        assert OrderRefund.objects.exists()
        assert OrderRefund.objects.count() == 1
        refund = OrderRefund.objects.first()
        assert refund.payment == payment
        assert refund.state == OrderRefund.REFUND_STATE_CREATED
        assert refund.info_data == {
            "currency_type": "ETH - L1",
            "amount": "100",
            "wallet_address": "0x0000000000000000000000000000000000000001",
        }


WALLET_ADDRESSES = [
    "0x0000000000000000000000000000000000000001",
    "0x0000000000000000000000000000000000000002",
    "0x0000000000000000000000000000000000000003",
    "0x0000000000000000000000000000000000000004",
    "0x0000000000000000000000000000000000000005",
]


@pytest.mark.django_db
def test_refund_wallets_filtered_correctly(
    event, organizer, create_admin_client, get_organizer_scope, get_order_and_payment
):
    WalletAddress.objects.bulk_create(
        [
            WalletAddress(event=event, hex_address=address)
            for address in WALLET_ADDRESSES
        ]
    )
    client = create_admin_client(event, email="admin@example.com")

    for _ in range(len(WALLET_ADDRESSES)):
        order, payment = get_order_and_payment(
            payment_kwargs={
                "state": OrderPayment.PAYMENT_STATE_CONFIRMED,
                "provider": "ethereum",
            },
            info_data={"amount": "100", "currency_type": "ETH - L1"},
        )
        WalletAddress.objects.get_for_order_payment(payment)
        make_refund(client, event, order, payment, organizer)

    with get_organizer_scope():
        unconfirmed_addresses = (
            WalletAddress.objects.all().for_event(event).unconfirmed_refunds()
        )

        assert len(unconfirmed_addresses) == len(WALLET_ADDRESSES)

        visited_wallets = set()
        for wallet_address in unconfirmed_addresses:
            assert wallet_address.hex_address not in visited_wallets
            assert wallet_address.hex_address in WALLET_ADDRESSES
            visited_wallets.add(wallet_address.hex_address)
