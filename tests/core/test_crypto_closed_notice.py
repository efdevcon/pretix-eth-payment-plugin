"""After the crypto rail closes (the provider's "Available until" has passed,
or the order holds a card-only `crypto_disabled` item), an unpaid crypto order
must not leave its buyer in front of a wallet UI whose endpoints now refuse
them: the pay page shows a notice with a way out, and the order page stops
saying "Waiting for payment to be sent."

A recorded transaction keeps the old behaviour (it is being verified), and a
buyer who was already quoted is told not to pay twice.
"""
import datetime

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone
from django_scopes import scope
from pretix.base.reldate import RelativeDateWrapper

from pretix_eth.payment import WalletConnectPayment

CLOSED = 'Crypto payment is no longer available for this order.'
DO_NOT_PAY_TWICE = 'Do not pay again.'


def _close_window(event):
    event.settings.set(
        'payment_walletconnect__availability_date',
        RelativeDateWrapper(timezone.now() - datetime.timedelta(days=1)),
    )


def _request(event, order):
    request = RequestFactory().get(f'/order/{order.code}/{order.secret}/pay/1/confirm')
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    return request


def _confirm_html(event, order, payment):
    with scope(organizer=event.organizer):
        return WalletConnectPayment(event).checkout_confirm_render(
            _request(event, order), order=order, info_data=payment.info_data,
        )


def _pending_html(event, order, payment):
    with scope(organizer=event.organizer):
        return WalletConnectPayment(event).payment_pending_render(_request(event, order), payment)


def _quote(seconds_left):
    now = int(timezone.now().timestamp())
    return {'quote_id': 'q1', 'expires_at': now + seconds_left}


@pytest.mark.django_db
def test_crypto_closed_for_order_follows_the_window(event, get_order_and_payment):
    order, _ = get_order_and_payment()
    with scope(organizer=event.organizer):
        assert WalletConnectPayment(event).crypto_closed_for_order(order) is False
    _close_window(event)
    with scope(organizer=event.organizer):
        assert WalletConnectPayment(event).crypto_closed_for_order(order) is True


@pytest.mark.django_db
def test_pay_page_shows_closed_notice_instead_of_wallet_ui(event, get_order_and_payment):
    _close_window(event)
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _confirm_html(event, order, payment)
    assert CLOSED in html
    assert 'wc-payment-root' not in html
    # Nothing to confirm on this page: the notice hides Pretix's own submit button.
    assert 'checkout-button-row' in html
    assert DO_NOT_PAY_TWICE not in html


@pytest.mark.django_db
def test_pay_page_warns_quoted_buyers_not_to_pay_twice(event, get_order_and_payment):
    _close_window(event)
    order, payment = get_order_and_payment(
        payment_kwargs={'state': 'created'}, info_data={'quote': _quote(-60)},
    )
    assert DO_NOT_PAY_TWICE in _confirm_html(event, order, payment)


@pytest.mark.django_db
def test_pay_page_offers_card_when_the_change_page_does(event, get_order_and_payment):
    event.plugins = 'pretix_eth,pretix.plugins.stripe'
    event.save()
    event.settings.set('payment_stripe__enabled', True)
    event.settings.set('payment_stripe_method_card', True)
    _close_window(event)
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _confirm_html(event, order, payment)
    assert 'Pay by card' in html
    assert f'/order/{order.code}/{order.secret}/pay/change' in html


@pytest.mark.django_db
def test_pay_page_without_other_method_has_no_switch_button(event, get_order_and_payment):
    """Only walletconnect is enabled on the fixture event."""
    _close_window(event)
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _confirm_html(event, order, payment)
    assert 'Pay by card' not in html
    assert 'Choose another payment method' not in html


@pytest.mark.django_db
def test_pay_page_keeps_wallet_ui_for_a_recorded_transaction(event, get_order_and_payment):
    _close_window(event)
    order, payment = get_order_and_payment(
        payment_kwargs={'state': 'created'}, info_data={'tx_hash': '0x' + 'ab' * 32},
    )
    html = _confirm_html(event, order, payment)
    assert CLOSED not in html
    assert 'wc-payment-root' in html


@pytest.mark.django_db
def test_pay_page_keeps_wallet_ui_while_crypto_is_open(event, get_order_and_payment):
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _confirm_html(event, order, payment)
    assert CLOSED not in html
    assert 'wc-payment-root' in html


@pytest.mark.django_db
def test_order_page_says_crypto_is_closed(event, get_order_and_payment):
    _close_window(event)
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _pending_html(event, order, payment)
    assert CLOSED in html
    assert 'Waiting for payment to be sent.' not in html


@pytest.mark.django_db
def test_order_page_closed_notice_warns_quoted_buyers(event, get_order_and_payment):
    _close_window(event)
    order, payment = get_order_and_payment(
        payment_kwargs={'state': 'created'}, info_data={'quote': _quote(600)},
    )
    assert DO_NOT_PAY_TWICE in _pending_html(event, order, payment)


@pytest.mark.django_db
def test_order_page_unchanged_while_crypto_is_open(event, get_order_and_payment):
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _pending_html(event, order, payment)
    assert 'Waiting for payment to be sent.' in html
    assert CLOSED not in html


@pytest.mark.django_db
def test_order_page_recorded_transaction_still_says_verifying(event, get_order_and_payment):
    _close_window(event)
    order, payment = get_order_and_payment(
        payment_kwargs={'state': 'created'}, info_data={'tx_hash': '0x' + 'cd' * 32, 'chain_id': 1},
    )
    html = _pending_html(event, order, payment)
    assert 'being verified onchain' in html
    assert CLOSED not in html


SUPPORT = 'help@example.org'


@pytest.mark.django_db
def test_order_page_without_other_method_points_to_support(event, get_order_and_payment):
    """Only walletconnect is enabled on the fixture event: no button to point at."""
    event.settings.set('payment_walletconnect_support_email', SUPPORT)
    _close_window(event)
    order, payment = get_order_and_payment(payment_kwargs={'state': 'created'})
    html = _pending_html(event, order, payment)
    assert CLOSED in html
    assert 'Use the button below' not in html
    assert f'Write to {SUPPORT} with your order code {order.code}' in html


@pytest.mark.django_db
def test_support_email_is_given_once_to_a_quoted_buyer_with_no_other_method(event, get_order_and_payment):
    event.settings.set('payment_walletconnect_support_email', SUPPORT)
    _close_window(event)
    order, payment = get_order_and_payment(
        payment_kwargs={'state': 'created'}, info_data={'quote': _quote(-60)},
    )
    for html in (_confirm_html(event, order, payment), _pending_html(event, order, payment)):
        assert DO_NOT_PAY_TWICE in html
        assert html.count(SUPPORT) == 1


@pytest.mark.django_db
def test_quoted_buyer_with_a_card_option_gets_the_support_line(event, get_order_and_payment):
    event.plugins = 'pretix_eth,pretix.plugins.stripe'
    event.save()
    event.settings.set('payment_stripe__enabled', True)
    event.settings.set('payment_stripe_method_card', True)
    event.settings.set('payment_walletconnect_support_email', SUPPORT)
    _close_window(event)
    order, payment = get_order_and_payment(
        payment_kwargs={'state': 'created'}, info_data={'quote': _quote(-60)},
    )
    html = _confirm_html(event, order, payment)
    assert 'Pay by card' in html
    assert html.count(SUPPORT) == 1
