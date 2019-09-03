import os

from django.core.management import call_command
import pytest

ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY')
skip_if_no_etherscan_api_key = pytest.mark.skipif(
    ETHERSCAN_API_KEY is None,
    reason='Etherscan api key is not set',
)

# Fake DAI deployment (LAI token)
GOERLI_TOKEN_ADDRESS = '0x57865b333088b4369c77e11b8c0f410ca2242e09'
GOERLI_WALLET_ADDRESS = '0xddd41b99968179d5f08b93a45eee20108c1b3f95'


@pytest.fixture
def get_orders_and_payments(get_order_and_payment):
    def _get_orders_and_payments(info_data_list):
        orders = []
        payments = []

        for info_data in info_data_list:
            order, payment = get_order_and_payment(info_data=info_data)

            orders.append(order)
            payments.append(payment)

        return orders, payments

    return _get_orders_and_payments


TEST_EQUAL_PAYMENTS = [
    {'currency_type': 'ETH', 'amount': int('000100000000000001', base=10)},
    {'currency_type': 'ETH', 'amount': int('000200000000000002', base=10)},
    {'currency_type': 'ETH', 'amount': int('001000000000000003', base=10)},  # Internal
    {'currency_type': 'ETH', 'amount': int('000100000000000004', base=10)},  # Internal
    {'currency_type': 'ETH', 'amount': int('000500000000000005', base=10)},
    {'currency_type': 'DAI', 'amount': int('100000000000000006', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('200000000000000007', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('300000000000000008', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('400000000000000009', base=10)},  # LAI token
]


@skip_if_no_etherscan_api_key
@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payments_works_for_equal_amounts(get_orders_and_payments):
    orders, payments = get_orders_and_payments(TEST_EQUAL_PAYMENTS)

    call_command(
        'confirm_payments',
        '--wallet-address', GOERLI_WALLET_ADDRESS,
        '--token-address', GOERLI_TOKEN_ADDRESS,
        '--api', 'etherscan-goerli',
        '--no-dry-run',
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PAID

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED


TEST_LOWER_PAYMENTS = [
    {'currency_type': 'ETH', 'amount': int('000090000000000001', base=10)},
    {'currency_type': 'ETH', 'amount': int('000100000000000002', base=10)},
    {'currency_type': 'ETH', 'amount': int('000900000000000003', base=10)},  # Internal
    {'currency_type': 'ETH', 'amount': int('000090000000000004', base=10)},  # Internal
    {'currency_type': 'ETH', 'amount': int('000490000000000005', base=10)},
    {'currency_type': 'DAI', 'amount': int('090000000000000006', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('100000000000000007', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('200000000000000008', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('300000000000000009', base=10)},  # LAI token
]


@skip_if_no_etherscan_api_key
@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payments_works_for_higher_amounts_on_blockchain(get_orders_and_payments):
    orders, payments = get_orders_and_payments(TEST_LOWER_PAYMENTS)

    call_command(
        'confirm_payments',
        '--wallet-address', GOERLI_WALLET_ADDRESS,
        '--token-address', GOERLI_TOKEN_ADDRESS,
        '--api', 'etherscan-goerli',
        '--no-dry-run',
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status == order.STATUS_PAID

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED


TEST_HIGHER_PAYMENTS = [
    {'currency_type': 'ETH', 'amount': int('000110000000000001', base=10)},
    {'currency_type': 'ETH', 'amount': int('000210000000000002', base=10)},
    {'currency_type': 'ETH', 'amount': int('001100000000000003', base=10)},  # Internal
    {'currency_type': 'ETH', 'amount': int('000110000000000004', base=10)},  # Internal
    {'currency_type': 'ETH', 'amount': int('000510000000000005', base=10)},
    {'currency_type': 'DAI', 'amount': int('110000000000000006', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('210000000000000007', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('310000000000000008', base=10)},  # LAI token
    {'currency_type': 'DAI', 'amount': int('410000000000000009', base=10)},  # LAI token
]


@skip_if_no_etherscan_api_key
@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payments_skips_lower_amounts_on_blockchain(get_orders_and_payments):
    orders, payments = get_orders_and_payments(TEST_HIGHER_PAYMENTS)

    call_command(
        'confirm_payments',
        '--wallet-address', GOERLI_WALLET_ADDRESS,
        '--token-address', GOERLI_TOKEN_ADDRESS,
        '--api', 'etherscan-goerli',
        '--no-dry-run',
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status != order.STATUS_PAID

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state != payment.PAYMENT_STATE_CONFIRMED


TEST_WRONG_CURRENCY_PAYMENTS = [
    {'currency_type': 'DAI', 'amount': int('000100000000000001', base=10)},
    {'currency_type': 'DAI', 'amount': int('000200000000000002', base=10)},
    {'currency_type': 'DAI', 'amount': int('001000000000000003', base=10)},  # Internal
    {'currency_type': 'DAI', 'amount': int('000100000000000004', base=10)},  # Internal
    {'currency_type': 'DAI', 'amount': int('000500000000000005', base=10)},
    {'currency_type': 'ETH', 'amount': int('100000000000000006', base=10)},  # LAI token
    {'currency_type': 'ETH', 'amount': int('200000000000000007', base=10)},  # LAI token
    {'currency_type': 'ETH', 'amount': int('300000000000000008', base=10)},  # LAI token
    {'currency_type': 'ETH', 'amount': int('400000000000000009', base=10)},  # LAI token
]


@skip_if_no_etherscan_api_key
@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payments_skips_wrong_currency_on_blockchain(get_orders_and_payments):
    orders, payments = get_orders_and_payments(TEST_WRONG_CURRENCY_PAYMENTS)

    call_command(
        'confirm_payments',
        '--wallet-address', GOERLI_WALLET_ADDRESS,
        '--token-address', GOERLI_TOKEN_ADDRESS,
        '--api', 'etherscan-goerli',
        '--no-dry-run',
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status != order.STATUS_PAID

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state != payment.PAYMENT_STATE_CONFIRMED


@skip_if_no_etherscan_api_key
@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_payments_does_dry_run_by_default(get_orders_and_payments):
    orders, payments = get_orders_and_payments(TEST_EQUAL_PAYMENTS)

    call_command(
        'confirm_payments',
        '--wallet-address', GOERLI_WALLET_ADDRESS,
        '--token-address', GOERLI_TOKEN_ADDRESS,
        '--api', 'etherscan-goerli',
    )

    for order in orders:
        order.refresh_from_db()
        assert order.status != order.STATUS_PAID

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state != payment.PAYMENT_STATE_CONFIRMED
