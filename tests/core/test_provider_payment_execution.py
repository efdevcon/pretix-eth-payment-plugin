import decimal
import time

import pytest

from django.test import RequestFactory
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore
from eth_utils import to_hex

from pretix.base.models import Order, OrderPayment
from pretix.base.payment import PaymentException

from pretix_eth.providers import (
    TokenProviderAPI,
    Transfer,
    TransactionProviderAPI,
    Transaction,
)


ZERO_HASH = b'\x00' * 32
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
ETH_ADDRESS = '0xeee0123400000000000000000000000000000000'
DAI_ADDRESS = '0xda10123400000000000000000000000000000000'


class FixtureTransactionProvider(TransactionProviderAPI):
    def __init__(self, transaction):
        self._transaction = transaction

    def get_transaction(self, from_address):
        return self._transaction


class FixtureTokenProvider(TokenProviderAPI):
    def __init__(self, transfer):
        self._transfer = transfer

    def get_ERC20_transfer(self, from_address):
        return self._transfer


@pytest.fixture
def order_and_payment(transactional_db, event):
    order = Order.objects.create(
        event=event,
        email='test@example.com',
        locale='en_US',
        datetime=timezone.now(),
        total=decimal.Decimal('100.00'),
        status=Order.STATUS_PENDING,
    )
    payment = OrderPayment.objects.create(
        order=order,
        amount='100.00',
        state=OrderPayment.PAYMENT_STATE_PENDING,
    )
    return order, payment


@pytest.mark.django_db
def test_provider_execute_successful_payment_in_ETH(provider, order_and_payment):
    order, payment = order_and_payment

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('ETH_RATE', '0.004')

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_currency_type'] = 'ETH'
    session['payment_ethereum_time'] = int(time.time()) - 10
    session['payment_ethereum_amount'] = 100

    request = factory.get('/checkout')
    request.event = provider.event
    request.session = session

    provider.execute_payment(request, payment)

    order.refresh_from_db()
    payment.refresh_from_db()

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING


@pytest.mark.django_db
def test_provider_execute_successful_payment_in_DAI(provider, order_and_payment):
    order, payment = order_and_payment

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('xDAI_RATE', '0.004')

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_currency_type'] = 'DAI'
    session['payment_ethereum_time'] = int(time.time()) - 10
    session['payment_ethereum_amount'] = 100

    request = factory.get('/checkout')
    request.event = provider.event
    request.session = session

    provider.execute_payment(request, payment)

    order.refresh_from_db()
    payment.refresh_from_db()

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING
