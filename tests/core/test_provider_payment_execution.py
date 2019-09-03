import time

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
import pytest


@pytest.mark.django_db
def test_provider_execute_successful_payment_in_ETH(provider, get_order_and_payment):
    order, payment = get_order_and_payment()

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
def test_provider_execute_successful_payment_in_DAI(provider, get_order_and_payment):
    order, payment = get_order_and_payment()

    assert order.status == order.STATUS_PENDING
    assert payment.state == payment.PAYMENT_STATE_PENDING

    provider.settings.set('DAI_RATE', '0.004')

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
