import os

from django.core.management import call_command
import pytest
import time

from django.test import RequestFactory
from django.urls import reverse
from django_scopes import scopes_disabled

from pretix_eth.models import WalletAddress

from pretix.base.models import (
    Order,
    OrderPayment,
    OrderRefund,
)


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


def make_refund(client, event, order, payment, organizer, amount):
    url = reverse('control:event.order.refunds.start', kwargs={
        'event': event.slug,
        'organizer': organizer.slug,
        'code': order.code
    })

    client.post(url, {
        f'refund-{payment.id}': amount,
        'start-mode': 'full',
        'perform': True
    })

    with scopes_disabled():
        assert OrderRefund.objects.exists()
        refund = OrderRefund.objects.filter(order=order).first()
    return refund


def make_payment_refund(payment_info, provider, get_request_order_payment, client, organizer):
    order_kwargs = {
        'total': payment_info['amount'],
        'status': Order.STATUS_PAID,
    }
    payment_kwargs = {
        'amount': payment_info['amount'],
        'state': OrderPayment.PAYMENT_STATE_CONFIRMED,
        'provider': 'ethereum',
    }
    info_data = {
        'currency_type': payment_info['currency'],
        'time': int(time.time()),
        'amount': payment_info['amount']
    }
    request, order, payment = get_request_order_payment(
        order_kwargs=order_kwargs, payment_kwargs=payment_kwargs, info_data=info_data)
    provider.payment_pending_render(request, payment)

    refund = make_refund(client, order.event, order, payment, organizer, payment_info['amount'])

    return payment, refund


TEST_REFUND_SUCCESSFUL_DATA = [
    {'currency': 'ETH - Rinkeby', 'amount': int('1000', base=10),
     'hex_address': '0x1Cecc45BFa0045E0069153c8DbBC1CdEeC5Ea148'},  # Empty wallet
    {'currency': 'DAI - Rinkeby', 'amount': int('1000', base=10),
     'hex_address': '0x5dCa654ed4E8e22B993B813A0879506c8Db12791'}   # Empty wallet
]


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_refund_successful(provider, event, get_request_order_payment,
                                   create_admin_client, organizer, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})
    client = create_admin_client(event, email='admin@example.com')

    payments = []
    refunds = []
    for payment_info in TEST_REFUND_SUCCESSFUL_DATA:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        payment, refund = make_payment_refund(payment_info, provider,
                                              get_request_order_payment,
                                              client, organizer)
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED
        assert refund.state == refund.REFUND_STATE_CREATED

        payments.append(payment)
        refunds.append(refund)

    with scopes_disabled():
        call_command(
            'confirm_refunds',
            '--event-slug', event.slug,
            '--no-dry-run'
        )

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_REFUNDED

    for refund in refunds:
        refund.refresh_from_db()
        assert refund.state == refund.REFUND_STATE_DONE


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_refund_dry_run(provider, event, get_request_order_payment,
                                create_admin_client, organizer, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})
    client = create_admin_client(event, email='admin@example.com')

    payments = []
    refunds = []
    for payment_info in TEST_REFUND_SUCCESSFUL_DATA:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        payment, refund = make_payment_refund(payment_info, provider,
                                              get_request_order_payment,
                                              client, organizer)
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED
        assert refund.state == refund.REFUND_STATE_CREATED

        payments.append(payment)
        refunds.append(refund)

    with scopes_disabled():
        call_command(
            'confirm_refunds',
            '--event-slug', event.slug,
        )

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED

    for refund in refunds:
        refund.refresh_from_db()
        assert refund.state == refund.REFUND_STATE_CREATED


TEST_NOT_REFUNDED_YET = [
    {'currency': 'ETH - Rinkeby', 'amount': int('10000', base=10),
     'hex_address': '0xDb9574bf428A612fe13BEFFeB7F4bD8C73BF2D88'},  # Has about 10'000'000 wei
    {'currency': 'DAI - Rinkeby', 'amount': int('10000', base=10),
     'hex_address': '0x3d5091A1652e215c71C755BCfA97A08AFC9d6CB0'}   # Has about 32'035 wei
]


@pytest.mark.django_db(
    transaction=True,
    reset_sequences=True,
)
def test_confirm_refunds_not_refunded_yet(provider, event, get_request_order_payment,
                                          create_admin_client, organizer, pytestconfig):
    check_web3_provider(pytestconfig)
    provider.settings.set("NETWORK_RPC_URL", {"Rinkeby_RPC_URL": WEB3_PROVIDER_URI})
    client = create_admin_client(event, email='admin@example.com')

    payments = []
    refunds = []
    for payment_info in TEST_NOT_REFUNDED_YET:
        WalletAddress.objects.create(hex_address=payment_info['hex_address'], event=event)
        payment, refund = make_payment_refund(payment_info, provider,
                                              get_request_order_payment,
                                              client, organizer)
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED
        assert refund.state == refund.REFUND_STATE_CREATED

        payments.append(payment)
        refunds.append(refund)

    with scopes_disabled():
        call_command(
            'confirm_refunds',
            '--event-slug', event.slug,
            '--no-dry-run'
        )

    for payment in payments:
        payment.refresh_from_db()
        assert payment.state == payment.PAYMENT_STATE_CONFIRMED

    for refund in refunds:
        refund.refresh_from_db()
        assert refund.state == refund.REFUND_STATE_CREATED
