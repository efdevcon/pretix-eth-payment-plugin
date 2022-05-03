import pytest
import time

from pretix_eth.models import WalletAddress, WalletAddressError

from django.test import RequestFactory

hex_addresses = [
    "0x4257a60613500E8272b0d6151E6CCcAcf79E8Ff4",
    "0x7D3013fB1Abe40A7bfBAA5E826E0A178F01Ef2F9",
    "0x4B10a9cbE018B01Ef65B43c622fE0Bd08a8BA160",
    "0xf5773255D551156182e7F0E3A26bD8d0Bb0022B7",
    "0xF68b56523CF6ec929953159B67e250a98726349B",
]


@pytest.fixture
def get_request_and_payment(get_order_and_payment):
    def _create_request_and_payment():
        info_data = {
            "currency_type": "ETH - L1",
            "time": int(time.time()),
            "amount": 1,
            "token_rates": {"ETH_RATE": 3000},
        }
        _, payment = get_order_and_payment(info_data=info_data)

        factory = RequestFactory()
        request = factory.get("/checkout")
        request.session = {
            "payment_currency_type": "ETH - L1",
            "payment_time": int(time.time()),
            "payment_amount": 1,
        }

        return request, payment

    return _create_request_and_payment


@pytest.mark.django_db
def test_addresses_correctly_assigned(event, provider, get_request_and_payment):
    provider.settings.set("ETH_RATE", "1.0")

    assert WalletAddress.objects.filter(order_payment__isnull=True).count() == 0

    WalletAddress.objects.bulk_create(
        [WalletAddress(event=event, hex_address=address) for address in hex_addresses]
    )

    assert WalletAddress.objects.filter(order_payment__isnull=True).count() == len(
        hex_addresses
    )

    used_addresses = set()

    for _ in range(len(hex_addresses)):
        request, payment = get_request_and_payment()
        response_page = provider.payment_pending_render(request, payment)

        wallet_queryset = WalletAddress.objects.filter(order_payment=payment)
        assert wallet_queryset.count() == 1

        hex_address = wallet_queryset.first().hex_address

        assert hex_address in response_page
        assert hex_address in hex_addresses
        assert hex_address not in used_addresses

        used_addresses.add(hex_address)

    assert WalletAddress.objects.filter(order_payment__isnull=True).count() == 0


@pytest.mark.django_db
def test_address_already_assigned(event, provider, get_request_and_payment):
    provider.settings.set("ETH_RATE", "1.0")

    WalletAddress.objects.create(event=event, hex_address=hex_addresses[0])

    request, payment = get_request_and_payment()
    provider.payment_pending_render(request, payment)

    wallet_queryset = WalletAddress.objects.filter(order_payment=payment)
    assert wallet_queryset.count() == 1

    original_hex_address = wallet_queryset.first().hex_address

    provider.payment_pending_render(request, payment)
    wallet_queryset = WalletAddress.objects.filter(order_payment=payment)
    assert wallet_queryset.count() == 1

    current_hex_address = wallet_queryset.first().hex_address

    assert original_hex_address == current_hex_address


@pytest.mark.django_db
def test_no_address_available(provider, get_request_and_payment):
    provider.settings.set("ETH_RATE", "1.0")

    request, payment = get_request_and_payment()

    with pytest.raises(
        WalletAddressError, match="No wallet addresses remain that haven't been used"
    ):
        provider.payment_pending_render(request, payment)
