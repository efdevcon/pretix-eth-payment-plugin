import decimal
import pytest
from unittest import mock

from django.utils import timezone
from django_scopes import scopes_disabled
from pretix.base.models import Order, SalesChannel


@pytest.fixture
def buyer_order(event, django_db_reset_sequences):
    """A pending order on the event that the buyer can authenticate against
    (Phase A Fix 5 added `_check_buyer_order_access`)."""
    with scopes_disabled():
        sales_channel, _ = SalesChannel.objects.get_or_create(
            identifier='web',
            defaults={'name': 'Web Shop', 'method': 'web'},
        )
        return Order.objects.create(
            event=event,
            email='buyer@example.com',
            status=Order.STATUS_PENDING,
            total=decimal.Decimal('50.00'),
            code='OPT123',
            datetime=timezone.now(),
            sales_channel=sales_channel,
            locale='en',
        )


@pytest.mark.django_db
def test_payment_options_returns_400_when_query_missing(client):
    """Without organizer/event in the query string the helper rejects 400.
    (Pre-Phase-A this returned 404; the early-validation 400 is the same
    failure-mode signal for callers and avoids a needless DB lookup.)"""
    resp = client.get('/plugin/wc/payment-options/')
    assert resp.status_code == 400
    assert 'error' in resp.json()


@pytest.mark.django_db
def test_payment_options_returns_options_for_configured_event(client, event, buyer_order):
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
            f'&order_code={buyer_order.code}&order_secret={buyer_order.secret}'
        )

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert 'options' in data
    assert data['eth_available'] is True
    assert data['receive_address'].lower() == '0x' + '2' * 40
    # All 5 supported chains should have options
    chain_ids = {o['chain_id'] for o in data['options']}
    assert chain_ids == {1, 10, 137, 8453, 42161}


@pytest.mark.django_db
def test_payment_options_disables_eth_when_oracle_fails(client, event, buyer_order):
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')

    async def fake_price():
        return None  # oracle divergence / failure

    with mock.patch('pretix_eth.views.fetch_eth_price_usd', fake_price):
        resp = client.get(
            f'/plugin/wc/payment-options/?organizer={event.organizer.slug}&event={event.slug}'
            f'&order_code={buyer_order.code}&order_secret={buyer_order.secret}'
        )

    data = resp.json()
    assert data['eth_available'] is False
    assert data['eth_disabled_reason'] == 'oracle_unavailable_or_diverged'
    # No ETH options returned
    assert not any(o['symbol'] == 'ETH' for o in data['options'])
