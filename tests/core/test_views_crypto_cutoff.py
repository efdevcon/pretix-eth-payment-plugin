"""Server-side effects of the crypto cutoff ("Available until" on the
walletconnect provider) and of per-item `crypto_disabled` on the buyer-facing
endpoints and the item-pricing feed.

Guard rails: `verify` must keep working after the cutoff (a transaction
broadcast before midnight still settles), and the config helper the admin
manual-verify tool reuses must not learn about the window.
"""
import datetime
import json
import time
from decimal import Decimal

import pytest
from django.utils import timezone
from django_scopes import scopes_disabled
from pretix.base.models import Item, ItemMetaProperty, ItemMetaValue, Order, OrderPosition
from pretix.base.reldate import RelativeDateWrapper


UNAVAILABLE = 'walletconnect unavailable'


@pytest.fixture
def configured(event):
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')
    return event


def _close_window(event):
    event.settings.set(
        'payment_walletconnect__availability_date',
        RelativeDateWrapper(timezone.now() - datetime.timedelta(days=1)),
    )


def _pending_order(event, code='CUT001', with_challenge=False):
    with scopes_disabled():
        sc = event.organizer.sales_channels.get(identifier='web')
        order = Order.objects.create(
            event=event, email='buyer@example.com', status=Order.STATUS_PENDING,
            total=Decimal('50.00'), code=code, datetime=timezone.now(),
            expires=timezone.now(), sales_channel=sc, locale='en',
        )
        if with_challenge:
            payment = order.payments.create(provider='walletconnect', amount=order.total, state='created')
            expires_at = int(time.time()) + 600
            payment.info_data = {
                'challenge_nonce': 'nonce1',
                'challenge_message': f'Pretix ticket payment\nOrder: {order.code}\nNonce: nonce1\nExpires: {expires_at}',
                'challenge_expires_at': expires_at,
            }
            payment.save()
    return order


def _flagged_item(event, flag, name='Flagged'):
    with scopes_disabled():
        item = Item.objects.create(event=event, name=name, default_price=Decimal('100.00'))
        prop, _ = ItemMetaProperty.objects.get_or_create(event=event, name=flag, defaults={'default': ''})
        ItemMetaValue.objects.create(item=item, property=prop, value='true')
    return item


def _ids(event):
    return {'organizer': event.organizer.slug, 'event': event.slug}


def _post(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type='application/json')


# --- buyer endpoints -------------------------------------------------------

@pytest.mark.django_db
def test_payment_options_404_after_cutoff(client, configured):
    order = _pending_order(configured)
    _close_window(configured)
    resp = client.get(
        f'/plugin/wc/payment-options/?organizer={configured.organizer.slug}&event={configured.slug}'
        f'&order_code={order.code}&order_secret={order.secret}'
    )
    assert resp.status_code == 404
    assert resp.json()['error'] == UNAVAILABLE


@pytest.mark.django_db
def test_challenge_404_after_cutoff(client, configured):
    order = _pending_order(configured)
    _close_window(configured)
    resp = _post(client, '/plugin/wc/challenge/', {
        'order_code': order.code, 'order_secret': order.secret, **_ids(configured),
    })
    assert resp.status_code == 404
    assert resp.json()['error'] == UNAVAILABLE


@pytest.mark.django_db
def test_create_quote_404_after_cutoff(client, configured):
    order = _pending_order(configured, with_challenge=True)
    _close_window(configured)
    resp = _post(client, '/plugin/wc/create-quote/', {
        'order_code': order.code, 'order_secret': order.secret, **_ids(configured),
        'chain_id': 8453, 'symbol': 'USDC', 'nonce': 'nonce1', 'signature': '0xdead',
    })
    assert resp.status_code == 404
    assert resp.json()['error'] == UNAVAILABLE


@pytest.mark.django_db
def test_create_quote_404_when_order_holds_crypto_disabled_item(client, configured):
    order = _pending_order(configured, with_challenge=True)
    item = _flagged_item(configured, 'crypto_disabled')
    with scopes_disabled():
        OrderPosition.objects.create(order=order, item=item, price=item.default_price, positionid=1)
    resp = _post(client, '/plugin/wc/create-quote/', {
        'order_code': order.code, 'order_secret': order.secret, **_ids(configured),
        'chain_id': 8453, 'symbol': 'USDC', 'nonce': 'nonce1', 'signature': '0xdead',
    })
    assert resp.status_code == 404
    assert resp.json()['error'].startswith(UNAVAILABLE)


@pytest.mark.django_db
def test_verify_is_not_gated_by_cutoff(client, configured):
    """A buyer whose transaction was broadcast before midnight must still be
    able to settle it: verify never consults the availability window."""
    _pending_order(configured, with_challenge=True)
    _close_window(configured)
    resp = _post(client, '/plugin/wc/verify/', {
        **_ids(configured), 'quote_id': 'no-such-quote',
        'tx_hash': '0x' + 'a' * 64, 'chain_id': 8453,
    })
    assert resp.json().get('error') != UNAVAILABLE


@pytest.mark.django_db
def test_admin_config_gate_ignores_cutoff(configured):
    """`views_admin.admin_wc_verify` reuses `_wc_config_or_403`; manual
    verification of a pre-cutoff payment must keep working on day 1."""
    from pretix_eth.views import _wc_config_or_403
    _close_window(configured)
    provider, err = _wc_config_or_403(configured)
    assert err is None and provider is not None


# --- item pricing feed -----------------------------------------------------

def _pricing(client, event):
    return client.get(f'/plugin/wc/item-pricing/?organizer={event.organizer.slug}&event={event.slug}')


@pytest.mark.django_db
def test_item_pricing_reports_crypto_available(client, configured):
    assert _pricing(client, configured).json()['crypto_available'] is True
    _close_window(configured)
    assert _pricing(client, configured).json()['crypto_available'] is False


@pytest.mark.django_db
def test_item_pricing_reports_crypto_disabled_per_item(client, configured):
    flagged = _flagged_item(configured, 'crypto_disabled', name='Card only')
    with scopes_disabled():
        plain = Item.objects.create(event=configured, name='GA', default_price=Decimal('100.00'))
    rows = {r['id']: r for r in _pricing(client, configured).json()['items']}
    assert rows[flagged.id]['crypto_disabled'] is True
    assert rows[plain.id]['crypto_disabled'] is False


@pytest.mark.django_db
def test_item_pricing_reports_cart_crypto_blocked(client, configured):
    from pretix.base.models import CartPosition
    flagged = _flagged_item(configured, 'crypto_disabled')
    cart_id = 'testcart@cutoff'
    with scopes_disabled():
        CartPosition.objects.create(
            event=configured, cart_id=cart_id, item=flagged, price=flagged.default_price,
            datetime=timezone.now(), expires=timezone.now() + datetime.timedelta(minutes=30),
        )
    assert _pricing(client, configured).json()['cart_crypto_blocked'] is False
    session = client.session
    session['current_cart_event_{}'.format(configured.pk)] = cart_id
    session.save()
    assert _pricing(client, configured).json()['cart_crypto_blocked'] is True
