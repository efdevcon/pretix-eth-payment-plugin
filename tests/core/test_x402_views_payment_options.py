# tests/core/test_x402_views_payment_options.py
import json
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django_scopes import scopes_disabled

from pretix_eth import urls as _eth_urls

# The x402 buyer flow is disabled in production (routes commented out in
# pretix_eth/urls.py). These route-level tests skip themselves when the route
# isn't registered, and run again automatically once it's uncommented.
pytestmark = pytest.mark.skipif(
    not any('plugin/x402/payment-options' in str(getattr(p, 'pattern', '')) for p in _eth_urls.urlpatterns),
    reason='x402 buyer route disabled (commented out in pretix_eth/urls.py)',
)


@pytest.fixture
def pending_order_for_options(event):
    from pretix_eth.models import X402PendingOrder
    with scopes_disabled():
        return X402PendingOrder.objects.create(
            event=event,
            payment_reference='x402_opts',
            order_data={'email': 'a@b.c', 'tickets': []},
            total_usd=Decimal('10.00'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )


@pytest.mark.django_db
def test_payment_options_requires_wallet_and_ref(api_client, event):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)
    resp = api_client.post(
        '/plugin/x402/payment-options/',
        data=json.dumps({'organizer': event.organizer.slug, 'event': event.slug}),
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_payment_options_rich_shape_with_signing_request(api_client, event, pending_order_for_options, monkeypatch):
    event.settings.set('payment_walletconnect_payment_recipient', '0x' + '2' * 40)

    def fake_fetch(*, wallet, chain_ids, alchemy_key, zapper_api_key=None):
        return [
            {'chain_id': 8453, 'symbol': 'USDC', 'balance': '50000000', 'decimals': 6,
             'token_address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'},
            {'chain_id': 8453, 'symbol': 'ETH', 'balance': '1000000000000000000', 'decimals': 18,
             'token_address': None},
        ]
    monkeypatch.setattr('pretix_eth.views_x402.fetch_balances_for_wallet', fake_fetch)

    # Stub ETH price so ETH option appears
    from pretix_eth.pricing import EthPriceResult
    async def fake_eth_price():
        return EthPriceResult(price=2000.0, source='dual')
    monkeypatch.setattr('pretix_eth.views_x402.fetch_eth_price_usd', fake_eth_price, raising=False)

    # Disable chains we don't care about for this test to keep options list short
    for cid in (1, 10, 137, 42161):
        event.settings.set(f'payment_walletconnect_chain_{cid}', False)
    for sym in ('USDT0',):
        event.settings.set(f'payment_walletconnect_token_{sym}', False)

    resp = api_client.post(
        '/plugin/x402/payment-options/',
        data=json.dumps({
            'organizer': event.organizer.slug, 'event': event.slug,
            'paymentReference': 'x402_opts',
            'walletAddress': '0x' + '1' * 40,
        }),
        content_type='application/json',
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    opts = body['options']
    # Expect USDC + ETH on Base
    symbols = sorted(o['symbol'] for o in opts)
    assert 'USDC' in symbols
    assert 'ETH' in symbols

    # USDC option should have gasless signing request (EIP-712 typed data)
    usdc = next(o for o in opts if o['symbol'] == 'USDC')
    assert usdc['asset'].startswith('eip155:8453/erc20:0x833589')
    assert usdc['chainId'] == 'eip155:8453'
    assert usdc['chain'] == 'Base'
    assert usdc['sufficient'] is True
    assert usdc['amount'] == '10000000'  # $10 * 10^6
    assert usdc['signingRequest']['method'] == 'eth_signTypedData_v4'

    # ETH option should have eth_sendTransaction signing request
    eth = next(o for o in opts if o['symbol'] == 'ETH')
    assert eth['chainId'] == 'eip155:8453'
    assert eth['sufficient'] is True
    assert eth['signingRequest']['method'] == 'eth_sendTransaction'
    assert 'priceUsd' in eth
