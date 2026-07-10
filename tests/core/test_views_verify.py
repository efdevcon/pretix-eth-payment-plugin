import json
import time
from unittest import mock
import pytest
from django_scopes import scopes_disabled

from pretix_eth.models import WCPaymentAttempt


@pytest.fixture
def quoted_order(event, django_db_reset_sequences):
    """An order with a fully-built quote on its pending payment (post /create-quote)."""
    from datetime import timedelta
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
            code='VERIFY1',
            datetime=timezone.now(),
            # V51: verify re-checks `order.expires` inside the atomic block.
            # The fixture must set this to a future time so the happy-path
            # tests don't trip the deadline-elapsed reject.
            expires=timezone.now() + timedelta(hours=1),
            sales_channel=sc,
            locale='en',
        )
        payment = order.payments.create(
            provider='walletconnect', amount=order.total, state='created',
        )
        now = int(time.time())
        payment.info_data = {
            'quote': {
                'quote_id': 'q_test_12345',
                'order_code': order.code,
                'chain_id': 8453,
                'symbol': 'USDC',
                'token_address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
                'amount_raw': '50000000',
                'receive_address': '0x' + '2' * 40,
                'intended_payer': '0x' + '1' * 40,
                'eth_price_usd': None,
                'created_at': now,
                'expires_at': now + 600,
                'order_total_usd': '50.00',
                # Signer binding (post-create-quote); settlement re-validates it.
                'signature': '0x' + '11' * 65,
                'signed_message': 'Devcon ticket payment',
                'sig_chain_id': 8453,
                'payer_code_prefix': None,
            }
        }
        payment.save()
    return order


@pytest.fixture
def event_configured(event):
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')
    event.settings.set('payment_walletconnect_min_confirmations', 1)
    return event


TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


def _make_fake_w3(from_addr, to_addr, token, amount, block=100, head=105, status=1, block_ts=None):
    """Build a stub web3 client. `block_ts` defaults to "now" so the V49 quote
    freshness window check (block.timestamp ∈ [quote.created_at, expires_at])
    passes by default; tests that want to drive the V49 reject paths can pass
    a timestamp outside that window explicitly."""
    def pad(a):
        return '0x' + '0' * 24 + a[2:].lower()
    if block_ts is None:
        block_ts = int(time.time()) + 1  # one tick after quoted_order.created_at
    fake = mock.MagicMock()
    fake.eth.block_number = head
    fake.eth.get_transaction_receipt.return_value = {
        'status': status, 'blockNumber': block,
        'logs': [{
            'address': token,
            'topics': [TRANSFER_TOPIC, pad(from_addr), pad(to_addr)],
            'data': hex(amount)[2:].rjust(64, '0'),
        }],
    }
    fake_block = mock.MagicMock()
    fake_block.timestamp = block_ts
    fake.eth.get_block.return_value = fake_block
    return fake


@pytest.mark.django_db
def test_verify_rejects_invalid_tx_hash_format(client, event_configured, quoted_order):
    resp = client.post('/plugin/wc/verify/', data=json.dumps({
        'quote_id': 'q_test_12345', 'tx_hash': 'nope', 'chain_id': 8453,
        'organizer': event_configured.organizer.slug, 'event': event_configured.slug,
    }), content_type='application/json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_verify_rejects_reused_tx_hash(client, event_configured, quoted_order):
    WCPaymentAttempt.objects.create(
        tx_hash='0x' + 'a' * 64, quote_id='old', order_code='OLD1',
        payer='0x' + '1' * 40, chain_id=8453, state='completed',
    )
    resp = client.post('/plugin/wc/verify/', data=json.dumps({
        'quote_id': 'q_test_12345', 'tx_hash': '0x' + 'a' * 64, 'chain_id': 8453,
        'organizer': event_configured.organizer.slug, 'event': event_configured.slug,
    }), content_type='application/json')
    assert resp.status_code == 400
    assert 'already used' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_verify_rejects_chain_mismatch(client, event_configured, quoted_order):
    resp = client.post('/plugin/wc/verify/', data=json.dumps({
        'quote_id': 'q_test_12345', 'tx_hash': '0x' + 'b' * 64, 'chain_id': 1,
        'organizer': event_configured.organizer.slug, 'event': event_configured.slug,
    }), content_type='application/json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_verify_happy_path(client, event_configured, quoted_order):
    fake = _make_fake_w3(
        from_addr='0x' + '1' * 40,
        to_addr='0x' + '2' * 40,
        token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        amount=50_000_000,
    )
    with mock.patch('pretix_eth.views._get_web3', return_value=fake), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345',
            'tx_hash': '0x' + 'c' * 64,
            'chain_id': 8453,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
        }), content_type='application/json')

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['verified'] is True

    # WCPaymentAttempt row created
    assert WCPaymentAttempt.objects.filter(
        tx_hash='0x' + 'c' * 64, state='completed',
    ).exists()

    # Order was confirmed
    with scopes_disabled():
        quoted_order.refresh_from_db()
        payment = quoted_order.payments.first()
        assert payment.info_data.get('tx_hash') == '0x' + 'c' * 64
        assert payment.info_data.get('chain_id') == 8453


@pytest.mark.django_db
def test_verify_on_chain_failure(client, event_configured, quoted_order):
    # Recipient mismatch
    fake = _make_fake_w3(
        from_addr='0x' + '1' * 40,
        to_addr='0x' + '9' * 40,  # wrong
        token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        amount=50_000_000,
    )
    with mock.patch('pretix_eth.views._get_web3', return_value=fake), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345',
            'tx_hash': '0x' + 'd' * 64,
            'chain_id': 8453,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
        }), content_type='application/json')
    assert resp.status_code == 400
    body = resp.json()
    assert body['verified'] is False

    # No WCPaymentAttempt row
    assert not WCPaymentAttempt.objects.filter(tx_hash='0x' + 'd' * 64).exists()


from django.core.cache import cache as django_cache
from django.test import override_settings


LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-rate-limit',
    }
}


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_verify_rate_limits_after_many_attempts(client, event_configured, quoted_order, monkeypatch):
    # Override rate limit env var
    monkeypatch.setenv('WC_VERIFY_RATE_LIMIT_PER_MIN', '2')
    # Force views module to re-read the value
    import pretix_eth.views as views_mod
    monkeypatch.setattr(views_mod, 'RATE_LIMIT_PER_MIN', 2)

    django_cache.clear()  # ensure fresh counter

    payload = json.dumps({
        'quote_id': 'q_test_12345',
        'tx_hash': '0x' + 'e' * 64,
        'chain_id': 8453,
        'organizer': event_configured.organizer.slug,
        'event': event_configured.slug,
    })

    # First two attempts — go through to the verify path; should 400/404 etc. (not 429)
    r1 = client.post('/plugin/wc/verify/', data=payload, content_type='application/json')
    assert r1.status_code != 429
    r2 = client.post('/plugin/wc/verify/', data=payload, content_type='application/json')
    assert r2.status_code != 429

    # Third attempt exceeds limit
    r3 = client.post('/plugin/wc/verify/', data=payload, content_type='application/json')
    assert r3.status_code == 429

    django_cache.clear()
