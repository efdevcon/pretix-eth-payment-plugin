# tests/core/test_x402_views_relayer.py
import json
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django_scopes import scopes_disabled
from pretix_eth.models import X402PendingOrder
from pretix_eth import urls as _eth_urls

# The x402 buyer flow is disabled in production (routes commented out in
# pretix_eth/urls.py). These route-level tests skip themselves when the route
# isn't registered, and run again automatically once it's uncommented.
pytestmark = pytest.mark.skipif(
    not any('plugin/x402/relayer' in str(getattr(p, 'pattern', '')) for p in _eth_urls.urlpatterns),
    reason='x402 buyer route disabled (commented out in pretix_eth/urls.py)',
)


@pytest.fixture
def pending_x402_order(event):
    with scopes_disabled():
        return X402PendingOrder.objects.create(
            event=event,
            payment_reference='x402_prep1',
            order_data={'email': 'a@b.c'},
            total_usd=Decimal('10.00'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )


@pytest.mark.django_db
def test_prepare_authorization_builds_typed_data(api_client, event, pending_x402_order):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = api_client.post('/plugin/x402/relayer/prepare-authorization/', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_prep1',
        'from': '0x' + '1' * 40,
        'chain_id': 8453,
        'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['success'] is True
    td = body['typed_data']
    assert td['primaryType'] == 'TransferWithAuthorization'
    assert td['domain']['chainId'] == 8453
    assert td['message']['from'].lower() == '0x' + '1' * 40
    assert td['message']['to'].lower() == '0x' + '2' * 40
    assert int(td['message']['value']) == 10_000_000  # $10 * 10^6


@pytest.mark.django_db
def test_prepare_rejects_wrong_from(api_client, event, pending_x402_order):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = api_client.post('/plugin/x402/relayer/prepare-authorization/', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_prep1',
        'from': '0x' + '9' * 40,  # wrong wallet
        'chain_id': 8453, 'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_execute_transfer_calls_relayer(api_client, event, pending_x402_order, monkeypatch):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_relayer_private_key', '0xdeadbeef' * 8)

    from pretix_eth.x402.relayer import RelayerResult

    def fake_execute(**kwargs):
        return RelayerResult(tx_hash='0x' + 'c' * 64, chain_id=kwargs['chain_id'])
    monkeypatch.setattr('pretix_eth.views_x402.execute_transfer_with_authorization', fake_execute)

    auth = {
        'from': '0x' + '1' * 40, 'to': '0x' + '2' * 40, 'value': '10000000',
        'validAfter': 0, 'validBefore': 9_999_999_999,
        'nonce': '0x' + 'a' * 64,
    }
    sig = '0x' + 'a' * 64 + 'b' * 64 + '1c'
    resp = api_client.post('/plugin/x402/relayer/execute-transfer/', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_prep1',
        'authorization': auth,
        'signature': sig,
        'chain_id': 8453,
        'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['success'] is True
    assert body['txHash'] == '0x' + 'c' * 64
