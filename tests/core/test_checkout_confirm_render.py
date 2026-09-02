"""checkout_confirm_render → the <script id="wc-config"> JSON the wc_inject
bundle boots from.

Guards the server-side inputs of the empty-wallet exit (the change-payment
URL and the "what else could this buyer pay with" flags) and, more basically,
that the JSON stays parseable — a syntax slip in that template takes the whole
crypto checkout down.
"""
import json
import re

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from pretix_eth.payment import WalletConnectPayment

_CONFIG_RE = re.compile(
    r'<script id="wc-config" type="application/json">\s*(\{.*?\})\s*</script>', re.S,
)


def _render_config(event, order):
    request = RequestFactory().get(f'/order/{order.code}/{order.secret}/pay/1/')
    # pretix's presale context processor (theme CSS version tag) reads these
    # off the request the way its multidomain middleware would have set them,
    # and the providers' is_allowed() checks read the session.
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    html = WalletConnectPayment(event).checkout_confirm_render(request, order=order)
    m = _CONFIG_RE.search(html)
    assert m, 'wc-config script tag missing from rendered checkout'
    return json.loads(m.group(1))


@pytest.mark.django_db
def test_wc_config_carries_change_payment_url(event, get_order_and_payment):
    order, _ = get_order_and_payment()
    cfg = _render_config(event, order)
    assert cfg['changePaymentUrl'].endswith(f'/order/{order.code}/{order.secret}/pay/change')
    assert cfg['pretixOrderUrl'].endswith(f'/order/{order.code}/{order.secret}/')


@pytest.mark.django_db
def test_wc_config_reports_no_other_methods_when_crypto_only(event, get_order_and_payment):
    """Only walletconnect is enabled on the fixture event: the bundle must
    not promise a "pay by card" (or any) switch it can't deliver."""
    order, _ = get_order_and_payment()
    cfg = _render_config(event, order)
    assert cfg['cardPaymentAvailable'] is False
    assert cfg['otherPaymentMethodsAvailable'] is False


@pytest.mark.django_db
def test_wc_config_reports_card_when_stripe_card_is_enabled(event, get_order_and_payment):
    event.plugins = 'pretix_eth,pretix.plugins.stripe'
    event.save()
    event.settings.set('payment_stripe__enabled', True)
    event.settings.set('payment_stripe_method_card', True)
    order, _ = get_order_and_payment()
    cfg = _render_config(event, order)
    assert cfg['cardPaymentAvailable'] is True
    assert cfg['otherPaymentMethodsAvailable'] is True
