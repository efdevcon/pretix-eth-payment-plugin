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


# ---------------------------------------------------------------------------
# Same-order quote sweep (payment-churn recovery):
# a tx can settle against ANY quote this order minted — each candidate checked
# against all of its own bindings — but never against another order's quotes.
# ---------------------------------------------------------------------------

def _add_superseded_payment(order, *, quote_id, amount_raw, created_at,
                            expires_at, order_total_usd='50.00'):
    """A canceled wc payment holding a full earlier quote, as left behind by
    'change payment method' after a wallet hiccup."""
    with scopes_disabled():
        p = order.payments.create(
            provider='walletconnect', amount=order.total, state='canceled',
        )
        p.info_data = {
            'quote': {
                'quote_id': quote_id,
                'order_code': order.code,
                'chain_id': 8453,
                'symbol': 'USDC',
                'token_address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
                'amount_raw': str(amount_raw),
                'receive_address': '0x' + '2' * 40,
                'intended_payer': '0x' + '1' * 40,
                'eth_price_usd': None,
                'created_at': created_at,
                'expires_at': expires_at,
                'order_total_usd': order_total_usd,
                'signature': '0x' + '22' * 65,
                'signed_message': 'Devcon ticket payment',
                'sig_chain_id': 8453,
                'payer_code_prefix': None,
            }
        }
        p.save()
    return p


@pytest.mark.django_db
def test_verify_settles_via_superseded_payment_quote(client, event_configured, quoted_order):
    """Tx paid against an earlier (now canceled, wall-clock-expired) quote of
    the SAME order settles the current live payment: the buyer submits the
    CURRENT quote_id (all the client has), the sweep matches the old quote's
    own bindings, and the tx's block timestamp sits inside the OLD quote's
    window (V49) even though that window has since closed on the wall clock."""
    now = int(time.time())
    _add_superseded_payment(
        quoted_order, quote_id='q_old_aaa', amount_raw=49_000_000,
        created_at=now - 300, expires_at=now - 30,
    )
    fake = _make_fake_w3(
        from_addr='0x' + '1' * 40,
        to_addr='0x' + '2' * 40,
        token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        amount=49_000_000,          # matches the OLD quote, not the current one
        block_ts=now - 100,         # inside the old window, before the new quote
    )
    with mock.patch('pretix_eth.views._get_web3', return_value=fake), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345',    # the CURRENT quote (fresh payment)
            'tx_hash': '0x' + 'e' * 64,
            'chain_id': 8453,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
        }), content_type='application/json')

    assert resp.status_code == 200, resp.content
    assert resp.json()['verified'] is True
    with scopes_disabled():
        quoted_order.refresh_from_db()
        live = quoted_order.payments.get(provider='walletconnect', state='confirmed')
        assert live.info_data.get('quote_claimed_from_history') is True
        assert live.info_data.get('settled_quote_id') == 'q_old_aaa'
        # Amount recorded from the quote that actually matched the tx.
        assert live.info_data.get('amount') == '49000000'
    attempt = WCPaymentAttempt.objects.get(tx_hash='0x' + 'e' * 64)
    assert attempt.quote_id == 'q_old_aaa'


@pytest.mark.django_db
def test_verify_accepts_old_quote_id_after_pay_change(client, event_configured, quoted_order):
    """The client's mount-recovery resubmits the OLD quote_id after a reload:
    the extended lookup finds it on the canceled payment, and settlement lands
    on the order's live payment."""
    now = int(time.time())
    _add_superseded_payment(
        quoted_order, quote_id='q_old_bbb', amount_raw=49_500_000,
        created_at=now - 300, expires_at=now - 30,
    )
    fake = _make_fake_w3(
        from_addr='0x' + '1' * 40,
        to_addr='0x' + '2' * 40,
        token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        amount=49_500_000,
        block_ts=now - 100,
    )
    with mock.patch('pretix_eth.views._get_web3', return_value=fake), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_old_bbb',       # the SUPERSEDED quote's id
            'tx_hash': '0x' + 'f' * 64,
            'chain_id': 8453,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
        }), content_type='application/json')

    assert resp.status_code == 200, resp.content
    with scopes_disabled():
        quoted_order.refresh_from_db()
        # The LIVE payment got confirmed — never the canceled one.
        assert quoted_order.payments.filter(provider='walletconnect', state='confirmed').count() == 1
        assert quoted_order.payments.get(state='canceled').state == 'canceled'


@pytest.mark.django_db
def test_verify_rejects_quote_with_stale_order_total(client, event_configured, quoted_order):
    """A quote minted when the order total was different must never settle —
    at its old price or the new one."""
    now = int(time.time())
    _add_superseded_payment(
        quoted_order, quote_id='q_old_ccc', amount_raw=45_000_000,
        created_at=now - 300, expires_at=now - 30,
        order_total_usd='45.00',   # order.total is 50.00 now
    )
    fake = _make_fake_w3(
        from_addr='0x' + '1' * 40,
        to_addr='0x' + '2' * 40,
        token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        amount=45_000_000,
        block_ts=now - 100,
    )
    with mock.patch('pretix_eth.views._get_web3', return_value=fake), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345',
            'tx_hash': '0x' + 'a1' * 32,
            'chain_id': 8453,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
        }), content_type='application/json')

    assert resp.status_code == 400
    assert not WCPaymentAttempt.objects.filter(tx_hash='0x' + 'a1' * 32).exists()
    with scopes_disabled():
        quoted_order.refresh_from_db()
        assert not quoted_order.payments.filter(state='confirmed').exists()


@pytest.mark.django_db
def test_verify_sweep_never_crosses_orders(client, event_configured, quoted_order, event):
    """A tx matching ANOTHER order's quote must not settle this order: the
    sweep draws candidates exclusively from the order that minted the
    submitted quote_id."""
    from datetime import timedelta
    from pretix.base.models import Order
    from decimal import Decimal
    from django.utils import timezone

    now = int(time.time())
    with scopes_disabled():
        sc = event.organizer.sales_channels.get(identifier='web')
        other = Order.objects.create(
            event=event, email='other@example.com', status=Order.STATUS_PENDING,
            total=Decimal('50.00'), code='VERIFY2', datetime=timezone.now(),
            expires=timezone.now() + timedelta(hours=1), sales_channel=sc, locale='en',
        )
    _add_superseded_payment(
        other, quote_id='q_other_ddd', amount_raw=47_000_000,
        created_at=now - 300, expires_at=now - 30,
    )
    fake = _make_fake_w3(
        from_addr='0x' + '1' * 40,
        to_addr='0x' + '2' * 40,
        token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        amount=47_000_000,          # matches the OTHER order's quote only
        block_ts=now - 100,
    )
    with mock.patch('pretix_eth.views._get_web3', return_value=fake), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345',    # quoted_order's quote
            'tx_hash': '0x' + 'b2' * 32,
            'chain_id': 8453,
            'organizer': event_configured.organizer.slug,
            'event': event_configured.slug,
        }), content_type='application/json')

    assert resp.status_code == 400
    assert not WCPaymentAttempt.objects.filter(tx_hash='0x' + 'b2' * 32).exists()
    with scopes_disabled():
        quoted_order.refresh_from_db()
        other.refresh_from_db()
        assert not quoted_order.payments.filter(state='confirmed').exists()
        assert not other.payments.filter(state='confirmed').exists()


# ---------------------------------------------------------------------------
# Input guards that the candidate sweep must not weaken.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_verify_rejects_unsupported_chain_id(client, event_configured, quoted_order):
    """The web3 client is now built before the per-candidate chain check, and
    get_rpc_url raises for unknown chains — that must surface as a 400, not
    an unhandled 500."""
    resp = client.post('/plugin/wc/verify/', data=json.dumps({
        'quote_id': 'q_test_12345', 'tx_hash': '0x' + 'c' * 64, 'chain_id': 999,
        'organizer': event_configured.organizer.slug, 'event': event_configured.slug,
    }), content_type='application/json')
    assert resp.status_code == 400
    assert 'unsupported chain_id' in resp.json()['error']


def _make_unmined_w3():
    """web3 >= 5 raises TransactionNotFound for a hash the node has never seen
    (it does NOT return None) — the shape a typo'd or never-broadcast hash
    produces in production."""
    from web3.exceptions import TransactionNotFound
    fake = mock.MagicMock()
    fake.eth.block_number = 105
    fake.eth.get_transaction_receipt.side_effect = TransactionNotFound('Transaction not found.')
    fake.eth.get_transaction.side_effect = TransactionNotFound('Transaction not found.')
    return fake


def _set_quote_expiry(order, expires_at):
    with scopes_disabled():
        p = order.payments.get(provider='walletconnect', state='created')
        info = p.info_data
        info['quote']['expires_at'] = expires_at
        p.info_data = info
        p.save()


@pytest.mark.django_db
@pytest.mark.parametrize('expires_offset', [600, -30], ids=['live-quote', 'inside-grace'])
def test_verify_unmined_tx_stays_retryable_until_grace_elapses(
        client, event_configured, quoted_order, expires_offset):
    """An unmined hash while the quote is live — or expired by less than the
    indexer-lag grace — keeps the client polling with the retryable
    'tx not mined yet' contract rather than the generic 'RPC error' string."""
    _set_quote_expiry(quoted_order, int(time.time()) + expires_offset)
    with mock.patch('pretix_eth.views._get_web3', return_value=_make_unmined_w3()), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345', 'tx_hash': '0x' + 'd' * 64, 'chain_id': 8453,
            'organizer': event_configured.organizer.slug, 'event': event_configured.slug,
        }), content_type='application/json')
    assert resp.status_code == 400
    assert resp.json()['error'] == 'tx not mined yet'


@pytest.mark.django_db
def test_verify_unmined_tx_after_expiry_grace_is_terminal(client, event_configured, quoted_order):
    """Once the quote window plus grace has passed, a still-unmined hash can
    never satisfy the V49 block-timestamp binding: verify must answer the
    terminal 'quote expired' so the client stops polling (and stops spending
    an RPC call per tick), as it did before the sweep existed."""
    _set_quote_expiry(quoted_order, int(time.time()) - 300)
    with mock.patch('pretix_eth.views._get_web3', return_value=_make_unmined_w3()), \
         mock.patch('pretix_eth.views._revalidate_quote_signer', return_value=(True, '')):
        resp = client.post('/plugin/wc/verify/', data=json.dumps({
            'quote_id': 'q_test_12345', 'tx_hash': '0x' + 'd' * 64, 'chain_id': 8453,
            'organizer': event_configured.organizer.slug, 'event': event_configured.slug,
        }), content_type='application/json')
    assert resp.status_code == 400
    assert resp.json()['error'] == 'quote expired'
    assert not WCPaymentAttempt.objects.filter(tx_hash='0x' + 'd' * 64).exists()
