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

    # setup a transaction provider which returns a fixed transaction
    transaction = Transaction(
        hash=ZERO_HASH,
        sender=ZERO_ADDRESS,
        success=True,
        to=ETH_ADDRESS,
        timestamp=int(time.time()),
        value=100,
    )

    tx_provider = FixtureTransactionProvider(transaction)
    provider.transaction_provider = tx_provider
    assert provider.transaction_provider is tx_provider

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('ETH', ETH_ADDRESS)

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_txn_hash'] = to_hex(ZERO_HASH)
    session['payment_ethereum_currency_type'] = 'ETH'
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

    # setup a transfer provider which returns a fixed transfer
    transfer = Transfer(
        hash=ZERO_HASH,
        sender=ZERO_ADDRESS,
        success=True,
        to=DAI_ADDRESS,
        timestamp=int(time.time()),
        value=100,
    )

    token_provider = FixtureTokenProvider(transfer)
    provider.token_provider = token_provider
    assert provider.token_provider is token_provider

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('DAI', DAI_ADDRESS)

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_txn_hash'] = to_hex(ZERO_HASH)
    session['payment_ethereum_currency_type'] = 'DAI'
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
def test_cannot_replay_same_transaction(provider, order_and_payment):
    order, payment = order_and_payment

    # setup a transaction provider which returns a fixed transaction
    transaction = Transaction(
        hash=ZERO_HASH,
        sender=ZERO_ADDRESS,
        success=True,
        to=ETH_ADDRESS,
        timestamp=int(time.time()),
        value=100,
    )

    tx_provider = FixtureTransactionProvider(transaction)
    provider.transaction_provider = tx_provider
    assert provider.transaction_provider is tx_provider

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('ETH', ETH_ADDRESS)

    factory = RequestFactory()
    session = SessionStore()
    session.create()

    # setup all the necessary session data for the payment to be valid
    session['payment_ethereum_txn_hash'] = to_hex(ZERO_HASH)
    session['payment_ethereum_currency_type'] = 'ETH'
    session['payment_ethereum_time'] = int(time.time()) - 10
    session['payment_ethereum_amount'] = 100

    request = factory.get('/checkout')
    request.event = provider.event
    request.session = session

    provider.execute_payment(request, payment)

    order.refresh_from_db()
    payment.refresh_from_db()

    with pytest.raises(
        PaymentException,
        match=r'Transaction with hash .* already used for payment',
    ):
        provider.execute_payment(request, payment)
