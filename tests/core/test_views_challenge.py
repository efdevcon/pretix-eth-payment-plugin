import json
import pytest

from django.utils import timezone
from django_scopes import scopes_disabled
from pretix.base.models import Order, SalesChannel

import decimal


@pytest.fixture
def pending_order(event, django_db_reset_sequences):
    """Create a pending Order on the event, ready to be paid via walletconnect."""
    with scopes_disabled():
        sales_channel, _ = SalesChannel.objects.get_or_create(
            identifier='web',
            defaults={'name': 'Web Shop', 'method': 'web'},
        )
        order = Order.objects.create(
            event=event,
            email='buyer@example.com',
            status=Order.STATUS_PENDING,
            total=decimal.Decimal('50.00'),
            code='CHALL1',
            datetime=timezone.now(),
            sales_channel=sales_channel,
            locale='en',
        )
    return order


@pytest.mark.django_db
def test_challenge_requires_post(client):
    resp = client.get('/plugin/wc/challenge/')
    assert resp.status_code == 405


@pytest.mark.django_db
def test_challenge_missing_fields(client):
    resp = client.post(
        '/plugin/wc/challenge/',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_challenge_returns_nonce_and_message(client, event, pending_order):
    resp = client.post(
        '/plugin/wc/challenge/',
        data=json.dumps({
            'order_code': pending_order.code,
            'order_secret': pending_order.secret,
            'organizer': event.organizer.slug,
            'event': event.slug,
        }),
        content_type='application/json',
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert 'nonce' in body
    assert len(body['nonce']) > 10
    assert 'message' in body
    assert pending_order.code in body['message']
    assert 'expires_at' in body
    assert body['expires_at'] > 0

    # Verify the nonce was persisted to the payment's info_data
    with scopes_disabled():
        pending_order.refresh_from_db()
        payment = pending_order.payments.filter(provider='walletconnect').first()
        assert payment is not None
        assert payment.info_data.get('challenge_nonce') == body['nonce']


@pytest.mark.django_db
def test_challenge_rejects_wrong_secret(client, event, pending_order):
    resp = client.post(
        '/plugin/wc/challenge/',
        data=json.dumps({
            'order_code': pending_order.code,
            'order_secret': 'wrong',
            'organizer': event.organizer.slug,
            'event': event.slug,
        }),
        content_type='application/json',
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_challenge_order_not_found(client, event):
    resp = client.post(
        '/plugin/wc/challenge/',
        data=json.dumps({
            'order_code': 'NOPE1',
            'order_secret': 'xxx',
            'organizer': event.organizer.slug,
            'event': event.slug,
        }),
        content_type='application/json',
    )
    assert resp.status_code == 404
