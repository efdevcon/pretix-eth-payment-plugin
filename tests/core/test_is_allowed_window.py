"""`WalletConnectPayment.is_allowed` must honour Pretix's standard
"Available from" / "Available until" provider settings.

The settings form shows both fields (the plugin extends the base form), but
the provider used to override `is_allowed` without consulting them, so an
operator setting "Available until" saw no effect. Pretix compares dates in the
event timezone: "until 2 Nov" keeps the rail on for all of 2 Nov.
"""
import datetime

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone
from pretix.base.reldate import RelativeDate, RelativeDateWrapper

from pretix_eth.payment import WalletConnectPayment


def _request(event):
    request = RequestFactory().get('/checkout/payment/')
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    return request


def _abs(days_from_now):
    return RelativeDateWrapper(timezone.now() + datetime.timedelta(days=days_from_now))


@pytest.fixture
def configured(event):
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')
    return event


@pytest.mark.django_db
def test_allowed_inside_window(configured):
    assert WalletConnectPayment(configured).is_allowed(_request(configured)) is True


@pytest.mark.django_db
def test_not_allowed_after_availability_date(configured):
    configured.settings.set('payment_walletconnect__availability_date', _abs(-1))
    assert WalletConnectPayment(configured).is_allowed(_request(configured)) is False


@pytest.mark.django_db
def test_still_allowed_on_the_availability_date_itself(configured):
    configured.settings.set('payment_walletconnect__availability_date', _abs(0))
    assert WalletConnectPayment(configured).is_allowed(_request(configured)) is True


@pytest.mark.django_db
def test_not_allowed_before_availability_start(configured):
    configured.settings.set('payment_walletconnect__availability_start', _abs(1))
    assert WalletConnectPayment(configured).is_allowed(_request(configured)) is False


@pytest.mark.django_db
def test_relative_availability_date_is_honoured(configured):
    # The fixture event starts in 7 days; "8 days before the event" is yesterday.
    rel = RelativeDateWrapper(RelativeDate(days=8, time=None, base_date_name='date_from', is_after=False))
    configured.settings.set('payment_walletconnect__availability_date', rel)
    assert WalletConnectPayment(configured).is_allowed(_request(configured)) is False


@pytest.mark.django_db
def test_request_none_is_tolerated(configured):
    assert WalletConnectPayment(configured).is_allowed(None) is True
    configured.settings.set('payment_walletconnect__availability_date', _abs(-1))
    assert WalletConnectPayment(configured).is_allowed(None) is False


@pytest.mark.django_db
def test_missing_wallet_config_still_blocks(event):
    assert WalletConnectPayment(event).is_allowed(_request(event)) is False
