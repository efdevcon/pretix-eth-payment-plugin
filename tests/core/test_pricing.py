from unittest import mock
import pytest
import httpx
from pretix_eth.pricing import fetch_eth_price_usd


class _FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
    def raise_for_status(self):
        pass
    def json(self):
        return self._data


async def test_dual_oracle_agreement_returns_average():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        return _FakeResponse({'price': '2010.00'})
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is not None
    assert result.source == 'dual'
    assert result.price == pytest.approx(2005.0)


async def test_divergence_over_5pct_returns_none():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        return _FakeResponse({'price': '2200.00'})  # ~10% diff
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is None


async def test_both_fail_returns_none():
    async def fake_get(self, url, **kw):
        raise httpx.ConnectError('down')
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is None


async def test_one_oracle_down_returns_none():
    # Stricter behavior: if either oracle is unreachable, disable ETH
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        raise httpx.ConnectError('binance down')
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is None


from decimal import Decimal
from pretix_eth.pricing import usd_to_token_raw, build_quote


def test_usdc_50_dollars_is_50_million_raw():
    # 50.00 USD * 10^6 decimals = 50_000_000
    assert usd_to_token_raw(Decimal('50.00'), 'USDC', chain_id=8453, eth_price=None) == 50_000_000


def test_usdt0_raw_conversion_on_optimism():
    # USDT0 is only on Optimism (10) and Arbitrum (42161)
    assert usd_to_token_raw(Decimal('12.34'), 'USDT0', chain_id=10, eth_price=None) == 12_340_000


def test_usdt0_unsupported_chain_raises():
    import pytest
    with pytest.raises(ValueError):
        # Ethereum (1) doesn't have USDT0 — should raise because contract lookup returns None
        usd_to_token_raw(Decimal('50'), 'USDT0', chain_id=1, eth_price=None)


def test_eth_raw_conversion_uses_price():
    # $2000 order at $2000/ETH = 1 ETH = 10^18 wei
    assert usd_to_token_raw(Decimal('2000'), 'ETH', chain_id=8453, eth_price=2000.0) == 10**18


def test_eth_without_price_raises():
    import pytest
    with pytest.raises(ValueError):
        usd_to_token_raw(Decimal('50'), 'ETH', chain_id=8453, eth_price=None)




def test_build_quote_shape_usdc():
    quote = build_quote(
        order_code='ABC12',
        order_total_usd=Decimal('50.00'),
        chain_id=8453, symbol='USDC',
        payer='0x' + '1' * 40,
        receive_address='0x' + '2' * 40,
        eth_price=None, ttl_seconds=600,
    )
    assert quote['order_code'] == 'ABC12'
    assert quote['chain_id'] == 8453
    assert quote['symbol'] == 'USDC'
    assert quote['amount_raw'] == '50000000'  # string to avoid BigInt JSON issues
    assert quote['token_address'].lower() == '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
    assert quote['intended_payer'] == '0x' + '1' * 40
    assert quote['receive_address'] == '0x' + '2' * 40
    assert len(quote['quote_id']) > 10
    assert quote['expires_at'] > quote['created_at']
    assert quote['expires_at'] - quote['created_at'] == 600


def test_build_quote_eth_has_null_token_address():
    quote = build_quote(
        order_code='X',
        order_total_usd=Decimal('2000'),
        chain_id=8453, symbol='ETH',
        payer='0x' + '1' * 40,
        receive_address='0x' + '2' * 40,
        eth_price=2000.0,
    )
    assert quote['token_address'] is None
    assert quote['amount_raw'] == str(10**18)
    assert quote['eth_price_usd'] == 2000.0


async def test_fetch_pol_price_dual_oracle():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '0.80'}})
        return _FakeResponse({'price': '0.81'})
    with mock.patch('httpx.AsyncClient.get', fake_get):
        from pretix_eth.pricing import fetch_pol_price_usd
        result = await fetch_pol_price_usd()
    assert result is not None
    assert result.price == pytest.approx(0.805)
