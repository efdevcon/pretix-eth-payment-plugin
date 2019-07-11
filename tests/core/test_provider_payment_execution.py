import decimal
import time

import pytest

from django.test import RequestFactory
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore

from pretix.base.models import Order, OrderPayment

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
    def __init__(self, transactions):
        self._transactions = transactions

    def get_transactions(self, from_address):
        return self._transactions


class FixtureTokenProvider(TokenProviderAPI):
    def __init__(self, transfers):
        self._transfers = transfers

    def get_ERC20_transfers(self, from_address):
        return self._transfers


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

    # setup a transaction provider which returns a fixed list of transactions
    # which will satisfy our order conditions
    transactions = (
        Transaction(
            hash=ZERO_HASH,
            sender=ZERO_ADDRESS,
            success=True,
            to=ETH_ADDRESS,
            timestamp=int(time.time()),
            value=100,
        ),
    )
    tx_provider = FixtureTransactionProvider(transactions)
    provider.transaction_provider = tx_provider
    assert provider.transaction_provider is tx_provider

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('ETH', ETH_ADDRESS)

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_fm_address'] = ZERO_ADDRESS
    session['payment_ethereum_fm_currency'] = 'ETH'
    session['payment_ethereum_time'] = int(time.time()) - 10
    session['payment_ethereum_amount'] = 100

    request = factory.get('/checkout')
    request.event = provider.event
    request.session = session

    provider.execute_payment(request, payment)

    order.refresh_from_db()
    payment.refresh_from_db()

    assert order.status == order.STATUS_PAID
    assert payment.state == payment.PAYMENT_STATE_CONFIRMED


@pytest.mark.django_db
def test_provider_execute_successful_payment_in_DAI(provider, order_and_payment):
    order, payment = order_and_payment

    # setup a transaction provider which returns a fixed list of transactions
    # which will satisfy our order conditions
    transfers = (
        Transfer(
            hash=ZERO_HASH,
            sender=ZERO_ADDRESS,
            success=True,
            to=DAI_ADDRESS,
            timestamp=int(time.time()),
            value=100,
        ),
    )
    token_provider = FixtureTokenProvider(transfers)
    provider.token_provider = token_provider
    assert provider.token_provider is token_provider

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('DAI', DAI_ADDRESS)

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_fm_address'] = ZERO_ADDRESS
    session['payment_ethereum_fm_currency'] = 'DAI'
    session['payment_ethereum_time'] = int(time.time()) - 10
    session['payment_ethereum_amount'] = 100

    request = factory.get('/checkout')
    request.event = provider.event
    request.session = session

    provider.execute_payment(request, payment)

    order.refresh_from_db()
    payment.refresh_from_db()

    assert order.status == order.STATUS_PAID
    assert payment.state == payment.PAYMENT_STATE_CONFIRMED
