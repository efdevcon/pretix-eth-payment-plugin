import pytest
from unittest import mock


@pytest.mark.django_db
def test_payment_options_returns_404_when_event_missing(client):
    resp = client.get('/plugin/wc/payment-options/')
    assert resp.status_code == 404
    assert 'error' in resp.json()


@pytest.mark.django_db
def test_payment_options_returns_options_for_configured_event(client, event):
    # Configure the provider settings on the event
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'testproject')

    # Stub the ETH oracle to return a valid price (so ETH is enabled)
    from pretix_eth.pricing import EthPriceResult
    async def fake_price():
        return EthPriceResult(price=2000.0, source='dual')

    with mock.patch('pretix_eth.views.fetch_eth_price_usd', fake_price):
        resp = client.get(
            f'/plugin/wc/payment-options/?organizer={event.organizer.slug}&event={event.slug}'
        )

    assert resp.status_code == 200
    data = resp.json()
    assert 'options' in data
    assert data['eth_available'] is True
    assert data['receive_address'].lower() == '0x' + '2' * 40
    # All 5 supported chains should have options
    chain_ids = {o['chain_id'] for o in data['options']}
    assert chain_ids == {1, 10, 137, 8453, 42161}


@pytest.mark.django_db
def test_payment_options_disables_eth_when_oracle_fails(client, event):
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')

    async def fake_price():
        return None  # oracle divergence / failure

    with mock.patch('pretix_eth.views.fetch_eth_price_usd', fake_price):
        resp = client.get(
            f'/plugin/wc/payment-options/?organizer={event.organizer.slug}&event={event.slug}'
        )

    data = resp.json()
    assert data['eth_available'] is False
    assert data['eth_disabled_reason'] == 'oracle_unavailable_or_diverged'
    # No ETH options returned
    assert not any(o['symbol'] == 'ETH' for o in data['options'])
