# tests/core/test_x402_views_verify.py
import json
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django_scopes import scopes_disabled

from pretix_eth.models import X402PendingOrder, X402CompletedOrder
from pretix_eth import urls as _eth_urls

# The x402 buyer flow is disabled in production (routes commented out in
# pretix_eth/urls.py). These route-level tests skip themselves when the route
# isn't registered, and run again automatically once it's uncommented.
pytestmark = pytest.mark.skipif(
    not any('plugin/x402/verify' in str(getattr(p, 'pattern', '')) for p in _eth_urls.urlpatterns),
    reason='x402 buyer route disabled (commented out in pretix_eth/urls.py)',
)


@pytest.fixture
def pending_x402_for_verify(event):
    with scopes_disabled():
        return X402PendingOrder.objects.create(
            event=event,
            payment_reference='x402_v1',
            order_data={'email': 'a@b.c', 'tickets': [{'itemId': 1, 'quantity': 1}]},
            total_usd=Decimal('10.00'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )


@pytest.fixture
def event_with_recipient(event):
    recipient = '0xA163a78C0b811A984fFe1B98b4b1b95BAb24aAcD'
    event.settings.set('payment_walletconnect_payment_recipient', recipient)
    return event


@pytest.mark.django_db
def test_verify_rejects_invalid_tx_hash(api_client, event_with_recipient, pending_x402_for_verify):
    resp = api_client.post('/plugin/x402/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'payment_reference': 'x402_v1',
        'tx_hash': 'not-a-hash',
        'payer': '0x' + '1' * 40,
        'chain_id': 8453,
        'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_verify_rejects_reused_tx_hash(api_client, event_with_recipient, pending_x402_for_verify):
    with scopes_disabled():
        X402CompletedOrder.objects.create(
            event=event_with_recipient, tx_hash='0x' + 'a' * 64,
            payment_reference='existing', pretix_order_code='X',
            payer='0x' + '9' * 40, chain_id=8453,
            total_usd=Decimal('1'), token_symbol='USDC',
        )
    resp = api_client.post('/plugin/x402/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'payment_reference': 'x402_v1',
        'tx_hash': '0x' + 'a' * 64,
        'payer': '0x' + '1' * 40,
        'chain_id': 8453, 'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 400
    assert 'already used' in resp.json()['error'].lower()
