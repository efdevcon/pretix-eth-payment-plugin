import os

from django.core.management import call_command
import pytest
import time

from django.test import RequestFactory

from pretix_eth.models import WalletAddress


WEB3_PROVIDER_URI = os.environ.get('WEB3_PROVIDER_URI')


def check_web3_provider(pytesconfig):
    # If set to true, any pytest failures will be displayed as if they
    # happened in the function that called check_web3_provider.
    # Makes reading logs easier.
    __tracebackhide__ = True

    web3_required = pytesconfig.getoption('--require-web3')
    if not web3_required:
        pytest.skip(
            '--require-web3 flag is not set')

    if WEB3_PROVIDER_URI is None:
        pytest.fail(
            '--require-web3 flag is set, but WEB3_PROVIDER_URI is None')


@pytest.fixture
def get_request_order_payment(get_order_and_payment):
    def _create_request_and_payment(order_kwargs=None, payment_kwargs=None, info_data=None):
        order, payment = get_order_and_payment(order_kwargs=order_kwargs,
                                               payment_kwargs=payment_kwargs,
                                               info_data=info_data)
        factory = RequestFactory()
        request = factory.get('/checkout')
        request.session = {
            "payment_currency_type": info_data["currency_type"], 
            "payment_time"         : info_data["time"],
            "payment_amount"       : info_data["amount"],
        }
        return request, order, payment
    return _create_request_and_payment


def make_order_payment(payment_info, provider, get_request_order_payment):
    order_kwargs = {
        'total': payment_info['amount']
    }
    payment_kwargs = {
        'amount': payment_info['amount']
    }
    info_data = {
        'currency_type': payment_info['currency'],
        'time': int(time.time()),
        'amount': payment_info['amount']
    }
    request, order, payment = get_request_order_payment(
        order_kwargs=order_kwargs, payment_kwargs=payment_kwargs, info_data=info_data)
    provider.payment_pending_render(request, payment)

    return order, payment


TEST_ENOUGH_AMOUNT = [
    {'currency': 'ETH - Rinkeby', 'amount': int('1000', base=10),
     'hex_address': '0xb84AC43014d60AE5dCe5d36975eE461f31e953d3'},  # Has about 0.5 ETH
    {'currency': 'DAI - Rinkeby', 'amount': int('1000', base=10),
     'hex_address': '0x18FF3A11FAF05F83198A8724006975ce414872Bc'}   # Has about 48 DAI
]


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_enough(provider, event, get_request_order_payment, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})

    payments = []
    orders = []
    for payment_info in TEST_ENOUGH_AMOUNT:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        order, payment = make_order_payment(payment_info, provider, get_request_order_payment)
        payments.append(payment)
        orders.append(order)

    call_command(
        'confirm_payments',
        '--no-dry-run'
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PAID

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_dry_run(provider, event, get_request_order_payment, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})

    payments = []
    orders = []
    for payment_info in TEST_ENOUGH_AMOUNT:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        order, payment = make_order_payment(payment_info, provider, get_request_order_payment)
        payments.append(payment)
        orders.append(order)

    call_command(
        'confirm_payments',
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PENDING

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_PENDING


TEST_LOWER_AMOUNT = [
    {'currency': 'ETH - Rinkeby', 'amount': int('99000000', base=10),
     'hex_address': '0xDb9574bf428A612fe13BEFFeB7F4bD8C73BF2D88'},  # Has about 10'000'000 wei
    {'currency': 'DAI - Rinkeby', 'amount': int('99000000', base=10),
     'hex_address': '0x3d5091A1652e215c71C755BCfA97A08AFC9d6CB0'}   # Has about 32'035 wei
]


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_lower_amount(provider, event, get_request_order_payment, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})

    payments = []
    orders = []
    for payment_info in TEST_LOWER_AMOUNT:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        order, payment = make_order_payment(payment_info, provider, get_request_order_payment)
        payments.append(payment)
        orders.append(order)

    call_command(
        'confirm_payments',
        '--no-dry-run'
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PENDING

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_PENDING


TEST_WRONG_CURRENCY = [
    {'currency': 'DAI - Rinkeby', 'amount': int('1000', base=10),
     'hex_address': '0xb84AC43014d60AE5dCe5d36975eE461f31e953d3'},  # Has enough amount, but in ETH
    {'currency': 'ETH - Rinkeby', 'amount': int('1000', base=10),
     'hex_address': '0x18FF3A11FAF05F83198A8724006975ce414872Bc'}   # Has enough amount, but in DAI
]


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_wrong_currency(provider, event, get_request_order_payment, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})

    payments = []
    orders = []
    for payment_info in TEST_WRONG_CURRENCY:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        order, payment = make_order_payment(payment_info, provider, get_request_order_payment)
        payments.append(payment)
        orders.append(order)

    call_command(
        'confirm_payments',
        '--no-dry-run'
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PENDING

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_PENDING
