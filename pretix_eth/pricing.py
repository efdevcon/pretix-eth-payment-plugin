"""Dual-oracle ETH price. Ports devcon ethPrice.ts."""
import asyncio
import logging
import secrets
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Optional

import httpx
from django.core.cache import cache

log = logging.getLogger(__name__)

# How long a successful price quote stays cached. ETH/POL move <0.5% in 30s
# under normal market conditions, well inside our 5% divergence guard. With a
# 30s window the worst-case staleness is below the slippage we already absorb
# elsewhere, and oracle traffic per buyer drops by ~50-100x on busy events.
PRICE_CACHE_TTL_SECONDS = 30
ETH_PRICE_CACHE_KEY = 'pretix_eth:price:eth'
POL_PRICE_CACHE_KEY = 'pretix_eth:price:pol'

COINBASE_URL = 'https://api.coinbase.com/v2/prices/ETH-USD/spot'
# api.binance.us instead of api.binance.com — the .com endpoint returns HTTP 451
# from US-hosted prod, while api.binance.us responds globally with the same
# response shape. No geo-aware config needed.
BINANCE_URL = 'https://api.binance.us/api/v3/ticker/price?symbol=ETHUSDT'
KRAKEN_ETH_URL = 'https://api.kraken.com/0/public/Ticker?pair=ETHUSD'
BITSTAMP_ETH_URL = 'https://www.bitstamp.net/api/v2/ticker/ethusd/'
MAX_DIVERGENCE_PCT = 5.0


@dataclass
class EthPriceResult:
    price: float
    # Free-form label naming the oracles that agreed (e.g. "coinbase+kraken").
    # Was a Literal in the dual-only era — kept as str so future oracle
    # additions don't churn this type.
    source: str


async def _fetch_coinbase(client: httpx.AsyncClient) -> float:
    r = await client.get(COINBASE_URL, timeout=2.0)
    r.raise_for_status()
    data = r.json()
    p = float(data['data']['amount'])
    if p <= 0:
        raise ValueError('invalid coinbase price')
    return p


async def _fetch_binance(client: httpx.AsyncClient) -> float:
    r = await client.get(BINANCE_URL, timeout=2.0)
    r.raise_for_status()
    data = r.json()
    p = float(data['price'])
    if p <= 0:
        raise ValueError('invalid binance price')
    return p


async def _fetch_kraken_eth(client: httpx.AsyncClient) -> float:
    """Kraken ticker: returns last trade price under result.<pair>.c[0]. Pair
    key is `XETHZUSD` for ETH/USD. We `next(iter(...))` so we don't have to
    care about the exact key Kraken returns."""
    r = await client.get(KRAKEN_ETH_URL, timeout=2.0)
    r.raise_for_status()
    j = r.json()
    if j.get('error'):
        raise ValueError('kraken error: %s' % j['error'])
    pair = next(iter(j['result'].values()))
    p = float(pair['c'][0])
    if p <= 0:
        raise ValueError('invalid kraken price')
    return p


async def _fetch_bitstamp_eth(client: httpx.AsyncClient) -> float:
    """Bitstamp ticker: returns last trade price as the `last` field. EU-based
    (Luxembourg) — independent of US-host risk and Binance geo-blocking, so
    it complements Coinbase + Kraken nicely."""
    r = await client.get(BITSTAMP_ETH_URL, timeout=2.0)
    r.raise_for_status()
    p = float(r.json()['last'])
    if p <= 0:
        raise ValueError('invalid bitstamp price')
    return p


def _quorum_price(prices: dict, *, label: str) -> Optional[EthPriceResult]:
    """Return the average of the largest subset of `prices` that all agree
    within MAX_DIVERGENCE_PCT, requiring at least 2 sources. Used to ride
    through a single oracle being unreachable (e.g. Binance 451 from EU
    hosts) or wildly off (rare price-feed glitch)."""
    if len(prices) < 2:
        log.warning(
            '%s oracle: <2 sources available (got %s) -- disabling',
            label, list(prices.keys()),
        )
        return None
    items = sorted(prices.items(), key=lambda kv: kv[1])
    # Try the largest agreeing cluster first (all → any pair).
    for size in range(len(items), 1, -1):
        for start in range(0, len(items) - size + 1):
            window = items[start:start + size]
            vals = [v for _, v in window]
            avg = sum(vals) / len(vals)
            spread_pct = (max(vals) - min(vals)) / avg * 100 if avg else 0.0
            if spread_pct <= MAX_DIVERGENCE_PCT:
                names = '+'.join(k for k, _ in window)
                return EthPriceResult(price=avg, source=names)
    log.warning(
        '%s oracle: no 2-source agreement within %.1f%% -- disabling (prices=%s)',
        label, MAX_DIVERGENCE_PCT, prices,
    )
    return None


async def fetch_eth_price_usd() -> Optional[EthPriceResult]:
    """Return price as soon as ≥2 of {coinbase, binance, kraken, bitstamp}
    agree within 5%. Returns None only if fewer than 2 oracles respond OR no
    2 agree. Tolerates one or two oracles being unreachable — e.g. Binance
    geo-block from EU prod hosts (we still get coinbase + kraken + bitstamp).

    Cached for `PRICE_CACHE_TTL_SECONDS` (~30s) — at high checkout concurrency
    this is what keeps us under CoinGecko's free-tier rate limit (10-30 RPM)
    and avoids hammering the others. `None` results aren't cached so a
    transient outage gets retried on the next request rather than locked in
    for the full TTL."""
    cached = cache.get(ETH_PRICE_CACHE_KEY)
    if cached:
        return EthPriceResult(**cached)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _fetch_coinbase(client),
            _fetch_binance(client),
            _fetch_kraken_eth(client),
            _fetch_bitstamp_eth(client),
            return_exceptions=True,
        )
    names = ['coinbase', 'binance', 'kraken', 'bitstamp']
    prices = {}
    for name, r in zip(names, results):
        if isinstance(r, float):
            prices[name] = r
        else:
            log.info('ETH oracle %s failed: %r', name, r)
    result = _quorum_price(prices, label='ETH')
    if result is not None:
        cache.set(ETH_PRICE_CACHE_KEY, asdict(result), PRICE_CACHE_TTL_SECONDS)
    return result


# ---------------------------------------------------------------------------
# USD -> raw token conversion & quote builder
# ---------------------------------------------------------------------------

from pretix_eth.chains import get_token_contract


# ETH amounts get rounded to the nearest multiple of 10^10 wei (= 8
# fractional digits when divided by 10^18). The native 18-digit precision
# produces buyer-facing strings like `0.165017964616885856 ETH` — accurate
# but unreadable, and the trailing digits represent fractions of a
# millionth of a cent at any realistic ETH price. 10^10 wei resolution
# means the *quoted, signed, and verified* amount itself is the clean
# value; there's no display-vs-reality drift to reason about for
# security — the BigInt sent on-chain equals what the buyer sees.
#
# Rounding error bound at typical ETH prices: 5 × 10^9 wei ≈ $0.00002 at
# $4500/ETH — three orders of magnitude below cent precision. Either
# direction (we round to nearest, not floor) is acceptable for the buyer
# *and* merchant since the drift is well below the receivable precision
# of any downstream accounting.
ETH_AMOUNT_PRECISION_FLOOR_WEI = 10 ** 10


def usd_to_token_raw(usd_amount: Decimal, symbol: str, chain_id: int,
                     eth_price: Optional[float]) -> int:
    """Convert a USD amount (Decimal, e.g. 50.00) to raw token base units.

    Stablecoins (USDC, USDT0) are returned at full 6-decimal precision —
    their `usd_amount * 10**6` is already an integer cent count, no
    cleaning needed.

    ETH is rounded to `ETH_AMOUNT_PRECISION_FLOOR_WEI` granularity so the
    on-chain amount itself (not just its display) is a clean 8-decimal
    value. See the constant's comment for the rationale.
    """
    if symbol in ('USDC', 'USDT0'):
        contract = get_token_contract(chain_id, symbol)
        if contract is None:
            raise ValueError(f'no contract for {symbol} on chain {chain_id}')
        return int(usd_amount * (10 ** contract['decimals']))
    if symbol == 'ETH':
        if eth_price is None:
            raise ValueError('ETH conversion requires eth_price')
        eth_float = float(usd_amount) / eth_price
        raw = int(eth_float * 10**18)
        # Round-to-nearest at the precision floor. Banker's rounding isn't
        # needed because we're not in a streaming-statistical context;
        # standard +half//floor is fine and stays in pure integer math.
        floor = ETH_AMOUNT_PRECISION_FLOOR_WEI
        return ((raw + floor // 2) // floor) * floor
    raise ValueError(f'unsupported symbol: {symbol}')


def build_quote(*, order_code: str, order_total_usd: Decimal,
                chain_id: int, symbol: str, payer: str,
                receive_address: str, eth_price: Optional[float],
                ttl_seconds: int = 600) -> dict:
    """Build a payment quote dict for the given order + chain + token."""
    amount_raw = usd_to_token_raw(order_total_usd, symbol, chain_id, eth_price)
    contract = get_token_contract(chain_id, symbol)
    now = int(time.time())
    return {
        'quote_id': secrets.token_urlsafe(16),
        'order_code': order_code,
        'chain_id': chain_id,
        'symbol': symbol,
        'token_address': contract['address'] if contract else None,
        'amount_raw': str(amount_raw),
        'receive_address': receive_address,
        'intended_payer': payer,
        'eth_price_usd': eth_price,
        'created_at': now,
        'expires_at': now + ttl_seconds,
        'order_total_usd': str(order_total_usd),
    }


# ---------------------------------------------------------------------------
# POL/USD dual-oracle (parallels ETH/USD above)
# ---------------------------------------------------------------------------

COINBASE_POL_URL = 'https://api.coinbase.com/v2/prices/POL-USD/spot'
BINANCE_POL_URL = 'https://api.binance.us/api/v3/ticker/price?symbol=POLUSDT'
# Kraken doesn't list POL/USD spot. CoinGecko's free public endpoint returns
# (rebranded MATIC=) POL under the `polygon-ecosystem-token` id.
COINGECKO_POL_URL = (
    'https://api.coingecko.com/api/v3/simple/price'
    '?ids=polygon-ecosystem-token&vs_currencies=usd'
)


async def _fetch_coinbase_pol(client: httpx.AsyncClient) -> float:
    r = await client.get(COINBASE_POL_URL, timeout=2.0)
    r.raise_for_status()
    p = float(r.json()['data']['amount'])
    if p <= 0:
        raise ValueError('invalid coinbase POL price')
    return p


async def _fetch_binance_pol(client: httpx.AsyncClient) -> float:
    r = await client.get(BINANCE_POL_URL, timeout=2.0)
    r.raise_for_status()
    p = float(r.json()['price'])
    if p <= 0:
        raise ValueError('invalid binance POL price')
    return p


async def _fetch_coingecko_pol(client: httpx.AsyncClient) -> float:
    r = await client.get(COINGECKO_POL_URL, timeout=2.0)
    r.raise_for_status()
    p = float(r.json()['polygon-ecosystem-token']['usd'])
    if p <= 0:
        raise ValueError('invalid coingecko POL price')
    return p


async def fetch_pol_price_usd() -> Optional[EthPriceResult]:
    """Return POL price as soon as ≥2 of {coinbase, binance, coingecko} agree
    within 5%. Tolerates one oracle being unreachable (e.g. Binance geo-block).

    Same 30s cache as ETH — particularly important here because CoinGecko's
    free tier is the strictest of all our oracles (~10-30 RPM)."""
    cached = cache.get(POL_PRICE_CACHE_KEY)
    if cached:
        return EthPriceResult(**cached)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _fetch_coinbase_pol(client),
            _fetch_binance_pol(client),
            _fetch_coingecko_pol(client),
            return_exceptions=True,
        )
    names = ['coinbase', 'binance', 'coingecko']
    prices = {}
    for name, r in zip(names, results):
        if isinstance(r, float):
            prices[name] = r
        else:
            log.info('POL oracle %s failed: %r', name, r)
    result = _quorum_price(prices, label='POL')
    if result is not None:
        cache.set(POL_PRICE_CACHE_KEY, asdict(result), PRICE_CACHE_TTL_SECONDS)
    return result
