import json
import time
from unittest import mock
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from django_scopes import scopes_disabled


@pytest.fixture
def pending_order_with_challenge(event, django_db_reset_sequences):
    """Order with a challenge already issued (reproduces what /challenge does)."""
    from pretix.base.models import Order
    from decimal import Decimal
    from django.utils import timezone

    with scopes_disabled():
        sc = event.organizer.sales_channels.get(identifier='web')
        order = Order.objects.create(
            event=event,
            email='buyer@example.com',
            status=Order.STATUS_PENDING,
            total=Decimal('50.00'),
            code='QUOTE1',
            datetime=timezone.now(),
            expires=timezone.now(),
            sales_channel=sc,
            locale='en',
        )
        payment = order.payments.create(
            provider='walletconnect', amount=order.total, state='created',
        )
        nonce = 'testnonce123'
        expires_at = int(time.time()) + 600
        message = f'Pretix ticket payment\nOrder: {order.code}\nNonce: {nonce}\nExpires: {expires_at}'
        payment.info_data = {
            'challenge_nonce': nonce,
            'challenge_message': message,
            'challenge_expires_at': expires_at,
        }
        payment.save()
    return order


@pytest.fixture
def event_configured(event):
    """Add receive_address to the event settings."""
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')
    return event


@pytest.mark.django_db
def test_create_quote_recovers_payer_from_signature(
    client, event_configured, pending_order_with_challenge,
):
    order = pending_order_with_challenge
    with scopes_disabled():
        payment = order.payments.first()
        info = payment.info_data
    nonce = info['challenge_nonce']
    message = info['challenge_message']

    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text=message))
    sig_hex = signed.signature.hex()

    resp = client.post('/plugin/wc/create-quote/', data=json.dumps({
        'order_code': order.code,
        'order_secret': order.secret,
        'organizer': event_configured.organizer.slug,
        'event': event_configured.slug,
        'chain_id': 8453, 'symbol': 'USDC',
        'nonce': nonce, 'signature': sig_hex,
    }), content_type='application/json')

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert 'quote_id' in body
    assert body['intended_payer'].lower() == acct.address.lower()
    assert body['chain_id'] == 8453
    assert body['symbol'] == 'USDC'
    # $50 USDC at 6 decimals = 50_000_000 raw
    assert body['amount_raw'] == '50000000'


@pytest.mark.django_db
def test_create_quote_rejects_wrong_nonce(
    client, event_configured, pending_order_with_challenge,
):
    order = pending_order_with_challenge
    with scopes_disabled():
        payment = order.payments.first()
        message = payment.info_data['challenge_message']

    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text=message))

    resp = client.post('/plugin/wc/create-quote/', data=json.dumps({
        'order_code': order.code,
        'order_secret': order.secret,
        'organizer': event_configured.organizer.slug,
        'event': event_configured.slug,
        'chain_id': 8453, 'symbol': 'USDC',
        'nonce': 'wrong-nonce', 'signature': signed.signature.hex(),
    }), content_type='application/json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_quote_rejects_unsupported_combo(
    client, event_configured, pending_order_with_challenge,
):
    order = pending_order_with_challenge
    with scopes_disabled():
        payment = order.payments.first()
        nonce = payment.info_data['challenge_nonce']
        message = payment.info_data['challenge_message']

    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text=message))

    # USDT0 on Ethereum is NOT supported (we only support it on Optimism + Arbitrum)
    resp = client.post('/plugin/wc/create-quote/', data=json.dumps({
        'order_code': order.code,
        'order_secret': order.secret,
        'organizer': event_configured.organizer.slug,
        'event': event_configured.slug,
        'chain_id': 1, 'symbol': 'USDT0',
        'nonce': nonce, 'signature': signed.signature.hex(),
    }), content_type='application/json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_quote_eth_uses_oracle_price(
    client, event_configured, pending_order_with_challenge,
):
    order = pending_order_with_challenge
    with scopes_disabled():
        payment = order.payments.first()
        nonce = payment.info_data['challenge_nonce']
        message = payment.info_data['challenge_message']

    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text=message))

    from pretix_eth.pricing import EthPriceResult
    async def fake_price():
        return EthPriceResult(price=2500.0, source='dual')

    with mock.patch('pretix_eth.views.fetch_eth_price_usd', fake_price):
        resp = client.post('/plugin/wc/create-quote/', data=json.dumps({
            'order_code': order.code,
            'order_secret': order.secret,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
            'chain_id': 8453, 'symbol': 'ETH',
            'nonce': nonce, 'signature': signed.signature.hex(),
        }), content_type='application/json')

    assert resp.status_code == 200, resp.content
    body = resp.json()
    # $50 / $2500 = 0.02 ETH = 20_000_000_000_000_000 wei
    assert int(body['amount_raw']) == 20_000_000_000_000_000
    assert body['eth_price_usd'] == 2500.0
    assert body['token_address'] is None


@pytest.mark.django_db
def test_create_quote_eth_disabled_when_oracle_fails(
    client, event_configured, pending_order_with_challenge,
):
    order = pending_order_with_challenge
    with scopes_disabled():
        payment = order.payments.first()
        nonce = payment.info_data['challenge_nonce']
        message = payment.info_data['challenge_message']

    acct = Account.create()
    signed = acct.sign_message(encode_defunct(text=message))

    async def fake_price():
        return None

    with mock.patch('pretix_eth.views.fetch_eth_price_usd', fake_price):
        resp = client.post('/plugin/wc/create-quote/', data=json.dumps({
            'order_code': order.code,
            'order_secret': order.secret,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
            'chain_id': 8453, 'symbol': 'ETH',
            'nonce': nonce, 'signature': signed.signature.hex(),
        }), content_type='application/json')
    assert resp.status_code == 503
