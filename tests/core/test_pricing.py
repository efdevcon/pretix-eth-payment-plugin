from unittest import mock
import pytest
import httpx
from django.core.cache import cache
from pretix_eth.pricing import fetch_eth_price_usd


@pytest.fixture(autouse=True)
def _clear_price_cache():
    """The pricing layer caches successful results for 30s. Clear between
    tests so each one exercises the full fetch path with its own mock."""
    cache.delete('pretix_eth:price:eth')
    cache.delete('pretix_eth:price:pol')
    yield
    cache.delete('pretix_eth:price:eth')
    cache.delete('pretix_eth:price:pol')


class _FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
    def raise_for_status(self):
        pass
    def json(self):
        return self._data


def _kraken_ok(price: str):
    return _FakeResponse({'error': [], 'result': {'XETHZUSD': {'c': [price, '0.001']}}})


def _bitstamp_ok(price: str):
    return _FakeResponse({'last': price})


async def test_all_oracles_agree_returns_average():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        if 'binance' in url:
            return _FakeResponse({'price': '2010.00'})
        if 'kraken' in url:
            return _kraken_ok('2005.00')
        return _bitstamp_ok('2003.00')  # bitstamp
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is not None
    assert result.price == pytest.approx((2000 + 2010 + 2005 + 2003) / 4)
    # All four agreed within 5%
    for n in ('coinbase', 'binance', 'kraken', 'bitstamp'):
        assert n in result.source


async def test_divergence_over_5pct_returns_none():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        if 'binance' in url:
            return _FakeResponse({'price': '2200.00'})  # ~10% diff
        if 'kraken' in url:
            return _kraken_ok('2400.00')  # also wide
        return _bitstamp_ok('2600.00')  # also wide
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is None


async def test_all_fail_returns_none():
    async def fake_get(self, url, **kw):
        raise httpx.ConnectError('down')
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is None


async def test_one_oracle_down_others_agree_returns_price():
    """The geo-block scenario: Binance returns 451 from EU prod hosts. As long
    as the other oracles agree, ETH pricing must keep working."""
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        if 'binance' in url:
            raise httpx.HTTPStatusError(
                'binance geo-block', request=mock.MagicMock(), response=_FakeResponse({}, 451),
            )
        if 'kraken' in url:
            return _kraken_ok('2010.00')
        return _bitstamp_ok('2005.00')
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is not None
    assert 'coinbase' in result.source
    assert 'kraken' in result.source
    assert 'bitstamp' in result.source
    assert 'binance' not in result.source
    assert result.price == pytest.approx((2000 + 2010 + 2005) / 3)


async def test_only_one_oracle_up_returns_none():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        raise httpx.ConnectError('down')
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is None  # need at least 2 sources


async def test_successful_price_is_cached_and_failures_are_not():
    """Single biggest mitigation against rate-limited oracles (CoinGecko free
    tier, etc.): a successful price round-trip is cached for 30s, so high
    checkout concurrency doesn't translate into per-buyer oracle traffic.
    Failures are NOT cached so a transient outage gets retried immediately.

    Pretix's test settings ship `DummyCache` (no-op). To verify the wiring
    independently of the backend, patch `pretix_eth.pricing.cache` with an
    in-memory stand-in and observe set/get calls."""
    store = {}

    class FakeCache:
        def get(self, k):
            return store.get(k)

        def set(self, k, v, ttl):
            store[k] = v

        def delete(self, k):
            store.pop(k, None)

    fake_cache = FakeCache()

    async def fake_ok(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        if 'binance' in url:
            return _FakeResponse({'price': '2010.00'})
        if 'kraken' in url:
            return _kraken_ok('2005.00')
        return _bitstamp_ok('2003.00')

    # 1) First call: cache miss → hits oracles → caches the result
    with mock.patch('pretix_eth.pricing.cache', fake_cache), \
            mock.patch('httpx.AsyncClient.get', fake_ok):
        first = await fetch_eth_price_usd()
    assert first is not None
    assert 'pretix_eth:price:eth' in store

    # 2) Second call: cache hit → no httpx call (we'd raise if it tried)
    async def boom(self, url, **kw):
        raise AssertionError('oracle should not be hit on cache HIT')

    with mock.patch('pretix_eth.pricing.cache', fake_cache), \
            mock.patch('httpx.AsyncClient.get', boom):
        second = await fetch_eth_price_usd()
    assert second is not None
    assert second.price == first.price

    # 3) None results are NOT cached
    store.clear()

    async def fake_all_down(self, url, **kw):
        raise httpx.ConnectError('down')

    with mock.patch('pretix_eth.pricing.cache', fake_cache), \
            mock.patch('httpx.AsyncClient.get', fake_all_down):
        result = await fetch_eth_price_usd()
    assert result is None
    assert 'pretix_eth:price:eth' not in store  # NOT cached


async def test_outlier_dropped_when_others_agree():
    """If most oracles agree and one is wildly off, use the agreeing cluster."""
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '2000.00'}})
        if 'binance' in url:
            return _FakeResponse({'price': '2010.00'})
        if 'kraken' in url:
            return _kraken_ok('2005.00')
        return _bitstamp_ok('1500.00')  # outlier
    with mock.patch('httpx.AsyncClient.get', fake_get):
        result = await fetch_eth_price_usd()
    assert result is not None
    assert 'bitstamp' not in result.source
    assert result.price == pytest.approx((2000 + 2010 + 2005) / 3)


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


async def test_fetch_pol_price_three_oracles():
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '0.80'}})
        if 'binance' in url:
            return _FakeResponse({'price': '0.81'})
        return _FakeResponse({'polygon-ecosystem-token': {'usd': 0.805}})
    with mock.patch('httpx.AsyncClient.get', fake_get):
        from pretix_eth.pricing import fetch_pol_price_usd
        result = await fetch_pol_price_usd()
    assert result is not None
    assert result.price == pytest.approx(0.805)


async def test_fetch_pol_price_binance_geo_blocked():
    """Same scenario as ETH: Binance blocked, but Coinbase + CoinGecko keep POL alive."""
    async def fake_get(self, url, **kw):
        if 'coinbase' in url:
            return _FakeResponse({'data': {'amount': '0.80'}})
        if 'binance' in url:
            raise httpx.HTTPStatusError(
                'binance geo-block', request=mock.MagicMock(), response=_FakeResponse({}, 451),
            )
        return _FakeResponse({'polygon-ecosystem-token': {'usd': 0.81}})
    with mock.patch('httpx.AsyncClient.get', fake_get):
        from pretix_eth.pricing import fetch_pol_price_usd
        result = await fetch_pol_price_usd()
    assert result is not None
    assert result.price == pytest.approx(0.805)
