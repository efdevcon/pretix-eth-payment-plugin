import os

from django.core.management import call_command
import pytest
import time
from django.test import RequestFactory
from pretix_eth.models import SignedMessage 

WEB3_PROVIDER_URI = os.environ.get("WEB3_PROVIDER_URI")
# WEB3_PROVIDER_URI = 'https://goerli.infura.io/v3/8733c260b59e445e85ee90bd80d869aa'
# SINGLE_RECEIVER_ADDRESS = "0x0000000000000000000000000000000000000000"
SINGLE_RECEIVER_ADDRESS = '0x47ABC45600bFb8069f53E55638Da593313e352C3'


def check_web3_provider(pytesconfig):
    # If set to true, any pytest failures will be displayed as if they
    # happened in the function that called check_web3_provider.
    # Makes reading logs easier.
    __tracebackhide__ = True

    web3_required = pytesconfig.getoption("--require-web3")
    if not web3_required:
        pytest.skip("--require-web3 flag is not set")

    if WEB3_PROVIDER_URI is None:
        pytest.fail("--require-web3 flag is set, but WEB3_PROVIDER_URI is None")


@pytest.fixture
def get_request_order_payment(get_order_and_payment):
    def _create_request_and_payment(
        order_kwargs=None, payment_kwargs=None, info_data=None
    ):
        order, payment = get_order_and_payment(
            order_kwargs=order_kwargs,
            payment_kwargs=payment_kwargs,
            info_data=info_data,
        )
        factory = RequestFactory()
        request = factory.get("/checkout")
        request.session = {
            "payment_currency_type": info_data["currency_type"],
            "payment_time": info_data["time"],
            "payment_amount": info_data["amount"]
        }
        return request, order, payment

    return _create_request_and_payment


def make_order_payment(payment_info, provider, get_request_order_payment):
    order_kwargs = {"total": 0 } 
    payment_kwargs = {"amount": 0 } 

    info_data = {
        "currency_type": payment_info["currency"],
        "time": int(time.time()),
        "amount": payment_info["amount"]
    }

    request, order, payment = get_request_order_payment(
        order_kwargs=order_kwargs, payment_kwargs=payment_kwargs, info_data=info_data
    )
    provider.payment_pending_render(request, payment)

    return order, payment

TEST_ENOUGH_AMOUNT = [
    {
        "currency": "ETH - Goerli",
        "amount": 40000000000000, # Required amount in wei
        "signature": "0xf0c9df2bfb0c78754342a142cbafe58ff4cca3e0377c60d7596067abcbbd161c3641969f7135b29710408ab0a975d11e3ba0c609da0525a311937a6161db39461c",
        "transaction_hash": '0x0cfd2f6f75bd37bf3286ac957964e1671560963b5abc004fe71fd74cd6cb6e45'
    }, 
    {
        "currency": "DAI - Goerli",
        "amount": 100000000000000000, # 0.1 dai
        "signature": "0x3345154d1069fe35e0396366ef9d6960974d9351b3cd46b1c31420ba6549bea0092395380e9140ec7d158343b08a93b3dd6c41130b10c65a3d420cca0cfc5ccd1c",
        "transaction_hash": '0x196aaf0114721e1e94d661c903b2a7b957d25c936bf559d0eeca23d99914e3c7'
    },
]

@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_enough(
    provider, event, get_request_order_payment, pytestconfig
):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Goerli_RPC_URL": WEB3_PROVIDER_URI})
    provider.settings.set("SINGLE_RECEIVER_ADDRESS", SINGLE_RECEIVER_ADDRESS)

    payments = []
    orders = []

    for payment_info in TEST_ENOUGH_AMOUNT:
        order, payment = make_order_payment(
            payment_info, provider, get_request_order_payment
        )

        # Add signed message to each order
        message_obj = SignedMessage(
            signature=payment_info['signature'],
            sender_address=SINGLE_RECEIVER_ADDRESS,
            recipient_address=SINGLE_RECEIVER_ADDRESS,
            chain_id=5,
            order_payment=payment,
            transaction_hash=payment_info['transaction_hash'],
        )

        message_obj.save()
        payments.append(payment)
        orders.append(order)

    call_command("confirm_payments", "--no-dry-run")

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
def test_confirm_payment_dry_run(
    provider, event, get_request_order_payment, pytestconfig
):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Goerli_RPC_URL": WEB3_PROVIDER_URI})
    provider.settings.set("SINGLE_RECEIVER_ADDRESS", SINGLE_RECEIVER_ADDRESS)

    payments = []
    orders = []
    for payment_info in TEST_ENOUGH_AMOUNT:
        order, payment = make_order_payment(
            payment_info, provider, get_request_order_payment
        )
        payments.append(payment)
        orders.append(order)

    call_command(
        "confirm_payments",
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PENDING

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_PENDING


TEST_LOWER_AMOUNT = [
    {
        "currency": "ETH - Goerli",
        "amount": int("99000000", base=10),
    },  # Has about 10'000'000 wei
    {
        "currency": "DAI - Goerli",
        "amount": int("99000000", base=10),
    },  # Has about 32'035 wei
]


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_lower_amount(
    provider, event, get_request_order_payment, pytestconfig
):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Goerli_RPC_URL": WEB3_PROVIDER_URI})
    provider.settings.set("SINGLE_RECEIVER_ADDRESS", SINGLE_RECEIVER_ADDRESS)

    payments = []
    orders = []
    for payment_info in TEST_LOWER_AMOUNT:
        order, payment = make_order_payment(
            payment_info, provider, get_request_order_payment
        )
        payments.append(payment)
        orders.append(order)

    call_command("confirm_payments", "--no-dry-run")

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PENDING

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_PENDING


TEST_WRONG_CURRENCY = [
    {
        "currency": "DAI - Goerli",
        "amount": int("1000", base=10)
    },  # Has enough amount, but in ETH
    {
        "currency": "ETH - Goerli",
        "amount": int("1000", base=10)
    },  # Has enough amount, but in DAI
]

@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payment_wrong_currency(
    provider, event, get_request_order_payment, pytestconfig
):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Goerli_RPC_URL": WEB3_PROVIDER_URI})
    provider.settings.set("SINGLE_RECEIVER_ADDRESS", SINGLE_RECEIVER_ADDRESS)

    payments = []
    orders = []
    for payment_info in TEST_WRONG_CURRENCY:
        order, payment = make_order_payment(
            payment_info, provider, get_request_order_payment
        )
        payments.append(payment)
        orders.append(order)

    call_command("confirm_payments", "--no-dry-run")

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PENDING

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_PENDING
