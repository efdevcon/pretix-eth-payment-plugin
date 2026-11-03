"""UPI via Stripe Checkout (prototype): the order stays in the event currency,
Stripe's hosted page converts it for the buyer, and only a session read back
from Stripe's API can confirm, fail or re-open a payment.
"""
from decimal import Decimal

import pytest
import stripe
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django_scopes import scope
from pretix.base.models import Order, OrderPayment
from pretix.base.payment import PaymentException

from pretix_eth.payment_upi import STRIPE_API_VERSION, StripeCheckoutUPI
from pretix_eth.views_upi import upi_return, upi_webhook

KEY = 'sk_test_prototype'


def _session(**over):
    data = {
        'id': 'cs_test_1', 'object': 'checkout.session', 'status': 'open', 'payment_status': 'unpaid',
        'url': 'https://checkout.stripe.com/c/pay/cs_test_1', 'expires_at': 1_900_000_000,
        'amount_total': 10000, 'currency': 'usd', 'payment_intent': None, 'presentment_details': None,
    }
    data.update(over)
    return stripe.checkout.Session.construct_from(data, KEY)


PAID = dict(status='complete', payment_status='paid', payment_intent='pi_test_1',
            presentment_details={'presentment_amount': 885000, 'presentment_currency': 'inr'})


def _request(event, path='/', method='get', data=None):
    request = getattr(RequestFactory(), method)(path, data=data, content_type='application/json') \
        if method == 'post' else RequestFactory().get(path)
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


@pytest.fixture
def upi_event(event):
    event.currency = 'USD'
    event.save(update_fields=['currency'])
    event.settings.set('payment_stripe_secret_key', KEY)
    return event


@pytest.fixture
def upi_payment(upi_event, get_order_and_payment):
    def _make(info_data=None, state=OrderPayment.PAYMENT_STATE_CREATED):
        return get_order_and_payment(
            payment_kwargs={'provider': StripeCheckoutUPI.identifier, 'state': state},
            info_data=info_data,
        )
    return _make


@pytest.fixture
def stripe_calls(monkeypatch):
    """Fake `Session.create` / `Session.retrieve` with a record of each call."""
    calls = {'create': [], 'retrieve': [], 'next': _session()}

    def fake_create(**kwargs):
        calls['create'].append(kwargs)
        return calls['next']

    def fake_retrieve(session_id, **kwargs):
        calls['retrieve'].append((session_id, kwargs))
        return calls['next']

    monkeypatch.setattr(stripe.checkout.Session, 'create', fake_create)
    monkeypatch.setattr(stripe.checkout.Session, 'retrieve', fake_retrieve)
    return calls


@pytest.mark.django_db
def test_offered_only_with_a_stripe_key(event):
    event.settings.set('payment_stripe_checkout_upi_restrict_to_flagged_items', False)  # product rule tested elsewhere
    with scope(organizer=event.organizer):
        request = _request(event)
        assert StripeCheckoutUPI(event).is_allowed(request, total=Decimal('100')) is False
        event.settings.set('payment_stripe_secret_key', KEY)
        assert StripeCheckoutUPI(event).is_allowed(request, total=Decimal('100')) is True


@pytest.mark.django_db
def test_session_is_created_in_the_event_currency_with_adaptive_pricing(upi_event, upi_payment, stripe_calls):
    order, payment = upi_payment()
    with scope(organizer=upi_event.organizer):
        url = StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert url == 'https://checkout.stripe.com/c/pay/cs_test_1'
    (kwargs,) = stripe_calls['create']
    assert kwargs['api_key'] == KEY
    assert kwargs['stripe_version'] == STRIPE_API_VERSION
    assert kwargs['adaptive_pricing'] == {'enabled': True}
    assert kwargs['allowed_payment_method_types'] == ['upi', 'card']  # UPI alone is refused on a USD session
    (item,) = kwargs['line_items']
    assert item['price_data']['currency'] == 'usd'
    assert item['price_data']['unit_amount'] == 10000
    assert kwargs['metadata'] == {'organizer': 'ef', 'event': 'devcon', 'order': order.code, 'payment': str(payment.pk)}
    assert kwargs['customer_email'] == 'test@example.com'
    assert f'/plugin/upi/return/{order.code}/' in kwargs['success_url']
    assert kwargs['success_url'].endswith('?session_id={CHECKOUT_SESSION_ID}')
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CREATED
    assert payment.info_data['session_id'] == 'cs_test_1'


@pytest.mark.django_db
def test_methods_setting_controls_the_stripe_page(upi_event, upi_payment, stripe_calls):
    upi_event.settings.set('payment_stripe_checkout_upi_payment_methods', 'upi, card')
    _, payment = upi_payment()
    with scope(organizer=upi_event.organizer):
        StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert stripe_calls['create'][0]['allowed_payment_method_types'] == ['upi', 'card']

    upi_event.settings.set('payment_stripe_checkout_upi_payment_methods', '')
    _, payment = upi_payment()
    with scope(organizer=upi_event.organizer):
        StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert 'allowed_payment_method_types' not in stripe_calls['create'][1]

    # A list saved without card (before the form validated it) is repaired, not sent as is.
    upi_event.settings.set('payment_stripe_checkout_upi_payment_methods', 'upi')
    _, payment = upi_payment()
    with scope(organizer=upi_event.organizer):
        StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert stripe_calls['create'][2]['allowed_payment_method_types'] == ['upi', 'card']


def test_methods_field_refuses_a_list_without_card():
    from django.core.exceptions import ValidationError
    from pretix_eth.payment_upi import _validate_methods
    for ok in ('', 'card', 'upi,card', 'upi, card, link'):
        _validate_methods(ok)
    with pytest.raises(ValidationError):
        _validate_methods('upi')


@pytest.mark.django_db
def test_stripe_400_is_reported_as_a_setup_problem_not_an_outage(upi_event, upi_payment, monkeypatch):
    def rejected(**kwargs):
        raise stripe.error.InvalidRequestError('`payment_method_types` must include ...', 'payment_method_types')
    monkeypatch.setattr(stripe.checkout.Session, 'create', rejected)
    _, payment = upi_payment()
    with scope(organizer=upi_event.organizer), pytest.raises(PaymentException) as exc:
        StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert 'rejected the payment setup' in str(exc.value)
    assert 'trouble reaching' not in str(exc.value)


@pytest.mark.django_db
def test_retry_reuses_an_open_session(upi_event, upi_payment, stripe_calls):
    _, payment = upi_payment(info_data={'session_id': 'cs_test_1', 'session_url': 'https://checkout.stripe.com/c/pay/cs_test_1'})
    with scope(organizer=upi_event.organizer):
        url = StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert url == 'https://checkout.stripe.com/c/pay/cs_test_1'
    assert stripe_calls['create'] == []
    assert stripe_calls['retrieve'][0][0] == 'cs_test_1'


@pytest.mark.django_db
def test_retry_after_expiry_starts_a_new_session(upi_event, upi_payment, stripe_calls):
    _, payment = upi_payment(info_data={'session_id': 'cs_test_old'})
    stripe_calls['next'] = _session(id='cs_test_old', status='expired')
    with scope(organizer=upi_event.organizer):
        StripeCheckoutUPI(upi_event).execute_payment(_request(upi_event), payment)
    assert len(stripe_calls['create']) == 1
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CREATED


@pytest.mark.django_db
def test_return_confirms_a_paid_session(upi_event, upi_payment, stripe_calls):
    order, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    stripe_calls['next'] = _session(**PAID)
    with scope(organizer=upi_event.organizer):
        request = _request(upi_event, f'/plugin/upi/return/{order.code}/x/{payment.pk}/?session_id=cs_test_1')
        response = upi_return(request, order=order.code, secret_hash=order.tagged_secret('plugins:pretix_eth:upi'),
                              payment=payment.pk)
    assert response.status_code == 302
    assert f'/order/{order.code}/{order.secret}/' in response['Location']
    assert response['Location'].endswith('?paid=yes')
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED
    assert order.status == Order.STATUS_PAID
    assert payment.info_data['payment_intent'] == 'pi_test_1'
    assert payment.info_data['presentment'] == {'amount': 885000, 'currency': 'inr'}


@pytest.mark.django_db
def test_return_with_a_wrong_secret_is_a_404(upi_event, upi_payment, stripe_calls):
    from django.http import Http404
    order, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    stripe_calls['next'] = _session(**PAID)
    with scope(organizer=upi_event.organizer), pytest.raises(Http404):
        upi_return(_request(upi_event), order=order.code, secret_hash='0' * 64, payment=payment.pk)
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CREATED


@pytest.mark.django_db
def test_paid_session_with_another_amount_is_refused(upi_event, upi_payment, stripe_calls):
    order, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    stripe_calls['next'] = _session(**PAID, amount_total=9000)
    with scope(organizer=upi_event.organizer):
        with pytest.raises(PaymentException):
            StripeCheckoutUPI(upi_event).sync_payment(payment)
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CREATED
    assert payment.info_data['payment_intent'] == 'pi_test_1'  # kept for the operator to look at


@pytest.mark.django_db
def test_expired_session_fails_the_payment(upi_event, upi_payment, stripe_calls):
    _, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    stripe_calls['next'] = _session(status='expired')
    with scope(organizer=upi_event.organizer):
        StripeCheckoutUPI(upi_event).sync_payment(payment)
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_FAILED


@pytest.mark.django_db
def test_webhook_acts_on_what_stripe_says_not_on_the_body(upi_event, upi_payment, stripe_calls):
    order, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    body = {'type': 'checkout.session.completed', 'data': {'object': {
        'object': 'checkout.session', 'id': 'cs_test_1', 'payment_status': 'paid',
        'metadata': {'order': order.code, 'payment': str(payment.pk)},
    }}}
    with scope(organizer=upi_event.organizer):
        # Stripe's API still says unpaid: the body alone must not confirm anything.
        response = upi_webhook(_request(upi_event, '/plugin/upi/webhook/', 'post', body))
        assert response.status_code == 200
        payment.refresh_from_db()
        assert payment.state == OrderPayment.PAYMENT_STATE_CREATED

        stripe_calls['next'] = _session(**PAID)
        response = upi_webhook(_request(upi_event, '/plugin/upi/webhook/', 'post', body))
        assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED


@pytest.mark.django_db
def test_webhook_ignores_unknown_or_mismatched_sessions(upi_event, upi_payment, stripe_calls):
    order, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    stripe_calls['next'] = _session(**PAID)
    with scope(organizer=upi_event.organizer):
        for obj in (
            {'object': 'payment_intent', 'id': 'pi_x'},
            {'object': 'checkout.session', 'id': 'cs_other', 'metadata': {'order': order.code, 'payment': str(payment.pk)}},
            {'object': 'checkout.session', 'id': 'cs_test_1', 'metadata': {'order': order.code, 'payment': 'nope'}},
        ):
            response = upi_webhook(_request(upi_event, '/plugin/upi/webhook/', 'post', {'data': {'object': obj}}))
            assert response.status_code == 200
    assert stripe_calls['retrieve'] == []
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CREATED


@pytest.mark.django_db
def test_order_page_links_to_the_open_session_and_the_status_check(upi_event, upi_payment, stripe_calls):
    import time
    order, payment = upi_payment(info_data={
        'session_id': 'cs_test_1', 'session_url': 'https://checkout.stripe.com/c/pay/cs_test_1',
        'session_status': 'open', 'expires_at': int(time.time()) + 600,
    })
    with scope(organizer=upi_event.organizer):
        html = StripeCheckoutUPI(upi_event).payment_pending_render(_request(upi_event), payment)
    assert 'Continue with UPI' in html
    assert 'https://checkout.stripe.com/c/pay/cs_test_1' in html
    assert f'/plugin/upi/return/{order.code}/' in html  # "check the payment status" goes through the return view
    assert stripe_calls['retrieve'] == []  # rendering never calls Stripe

    payment.info_data = {**payment.info_data, 'expires_at': int(time.time()) - 1}
    payment.save(update_fields=['info'])
    with scope(organizer=upi_event.organizer):
        html = StripeCheckoutUPI(upi_event).payment_pending_render(_request(upi_event), payment)
    assert 'Continue with UPI' not in html
    assert f'/plugin/upi/return/{order.code}/' in html


@pytest.mark.django_db
def test_webhook_records_a_mismatch_without_asking_stripe_to_retry(upi_event, upi_payment, stripe_calls):
    order, payment = upi_payment(info_data={'session_id': 'cs_test_1'})
    stripe_calls['next'] = _session(**PAID, amount_total=9000)
    body = {'data': {'object': {'object': 'checkout.session', 'id': 'cs_test_1',
                                'metadata': {'order': order.code, 'payment': str(payment.pk)}}}}
    with scope(organizer=upi_event.organizer):
        response = upi_webhook(_request(upi_event, '/plugin/upi/webhook/', 'post', body))
    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CREATED


@pytest.mark.django_db
def test_control_panel_shows_the_rupee_amount(upi_event, upi_payment):
    _, payment = upi_payment(info_data={
        'session_id': 'cs_test_1', 'session_status': 'complete', 'payment_status': 'paid',
        'payment_intent': 'pi_test_1', 'presentment': {'amount': 885000, 'currency': 'inr'},
    })
    with scope(organizer=upi_event.organizer):
        html = StripeCheckoutUPI(upi_event).payment_control_render(_request(upi_event), payment)
    assert '8850.00 INR' in html
    assert 'https://dashboard.stripe.com/payments/pi_test_1' in html


@pytest.mark.django_db
def test_both_providers_are_registered(upi_event):
    with scope(organizer=upi_event.organizer):
        providers = upi_event.get_payment_providers()
    assert 'walletconnect' in providers
    assert isinstance(providers.get('stripe_checkout_upi'), StripeCheckoutUPI)
