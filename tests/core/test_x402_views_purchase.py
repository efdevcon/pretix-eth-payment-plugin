# tests/core/test_x402_views_purchase.py
import json
import pytest
from django_scopes import scopes_disabled

from pretix_eth import urls as _eth_urls

# The x402 buyer flow is disabled in production (routes commented out in
# pretix_eth/urls.py). These route-level tests skip themselves when the route
# isn't registered, and run again automatically once it's uncommented.
pytestmark = pytest.mark.skipif(
    not any('plugin/x402/purchase' in str(getattr(p, 'pattern', '')) for p in _eth_urls.urlpatterns),
    reason='x402 buyer route disabled (commented out in pretix_eth/urls.py)',
)


@pytest.mark.django_db
def test_purchase_creates_pending_order(api_client, event, monkeypatch):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_crypto_discount_percent', '0')

    # Stub Pretix ticket purchase info + event settings
    fake_ticket_info = {
        'tickets': [{'id': 1, 'name': 'GA', 'price': '50.00', 'available': True,
                     'isAdmission': True, 'requireVoucher': False, 'variations': []}],
        'questions': [],
        'event': {'currency': 'USD'},
    }
    monkeypatch.setattr(
        'pretix_eth.views_x402.get_ticket_purchase_info',
        lambda event: fake_ticket_info,
    )

    resp = api_client.post('/plugin/x402/purchase/', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'email': 'buyer@example.com',
        'intended_payer': '0x' + '1' * 40,
        'tickets': [{'itemId': 1, 'quantity': 1}],
    }), content_type='application/json')

    assert resp.status_code == 402
    body = resp.json()
    assert body.get('success') is True
    assert body['paymentRequired'] is True
    assert 'paymentReference' in body['paymentDetails']['payment']
    assert body['orderSummary']['total'] == '50.00'

    with scopes_disabled():
        from pretix_eth.models import X402PendingOrder
        assert X402PendingOrder.objects.filter(
            event=event, intended_payer='0x' + '1' * 40,
        ).exists()


@pytest.fixture
def _ticket_info_with_variation(monkeypatch):
    """A ticket that has an active variation at a higher price."""
    fake_ticket_info = {
        'tickets': [{
            'id': 1, 'name': 'GA', 'price': '50.00', 'available': True,
            'isAdmission': True, 'requireVoucher': False,
            'variations': [{'id': 99, 'name': 'Premium', 'price': '150.00'}],
        }],
        'questions': [],
        'event': {'currency': 'USD'},
    }
    monkeypatch.setattr(
        'pretix_eth.views_x402.get_ticket_purchase_info',
        lambda event: fake_ticket_info,
    )
    return fake_ticket_info


def _purchase(api_client, event, tickets, addons=None):
    body = {
        'organizer': event.organizer.slug, 'event': event.slug,
        'email': 'buyer@example.com',
        'intended_payer': '0x' + '1' * 40,
        'tickets': tickets,
    }
    if addons is not None:
        body['addons'] = addons
    return api_client.post('/plugin/x402/purchase/',
                           data=json.dumps(body),
                           content_type='application/json')


@pytest.mark.django_db
def test_purchase_rejects_zero_quantity(api_client, event, _ticket_info_with_variation):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = _purchase(api_client, event, tickets=[{'itemId': 1, 'quantity': 0}])
    assert resp.status_code == 400
    assert 'quantity' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_purchase_rejects_negative_quantity(api_client, event, _ticket_info_with_variation):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = _purchase(api_client, event, tickets=[{'itemId': 1, 'quantity': -5}])
    assert resp.status_code == 400
    assert 'quantity' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_purchase_rejects_excessive_quantity(api_client, event, _ticket_info_with_variation):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = _purchase(api_client, event, tickets=[{'itemId': 1, 'quantity': 9999}])
    assert resp.status_code == 400


@pytest.mark.django_db
def test_purchase_rejects_invalid_variation_id(api_client, event, _ticket_info_with_variation):
    """Providing a variation that isn't active for this item must be rejected,
    not silently fall back to base price (underpricing attack)."""
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = _purchase(api_client, event, tickets=[
        {'itemId': 1, 'quantity': 1, 'variationId': 12345},  # 12345 not a valid variation
    ])
    assert resp.status_code == 400
    assert 'variation' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_purchase_applies_variation_price(api_client, event, _ticket_info_with_variation):
    """A valid variationId uses the variation's price (not item base)."""
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = _purchase(api_client, event, tickets=[
        {'itemId': 1, 'quantity': 1, 'variationId': 99},
    ])
    assert resp.status_code == 402
    body = resp.json()
    # Variation price is $150, not the $50 base
    assert body['orderSummary']['total'] == '150.00'
