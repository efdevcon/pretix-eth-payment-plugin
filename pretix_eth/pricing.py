"""Dual-oracle ETH price. Ports devcon ethPrice.ts."""
import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Literal

import httpx

log = logging.getLogger(__name__)

COINBASE_URL = 'https://api.coinbase.com/v2/prices/ETH-USD/spot'
BINANCE_URL = 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT'
MAX_DIVERGENCE_PCT = 5.0


@dataclass
class EthPriceResult:
    price: float
    source: Literal['dual', 'coinbase', 'binance']


async def _fetch_coinbase(client: httpx.AsyncClient) -> float:
    r = await client.get(COINBASE_URL, timeout=5.0)
    r.raise_for_status()
    data = r.json()
    p = float(data['data']['amount'])
    if p <= 0:
        raise ValueError('invalid coinbase price')
    return p


async def _fetch_binance(client: httpx.AsyncClient) -> float:
    r = await client.get(BINANCE_URL, timeout=5.0)
    r.raise_for_status()
    data = r.json()
    p = float(data['price'])
    if p <= 0:
        raise ValueError('invalid binance price')
    return p


async def fetch_eth_price_usd() -> Optional[EthPriceResult]:
    """Return price if both oracles agree within 5%. Return None if either
    oracle is unreachable or they diverge too much -- callers disable ETH."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _fetch_coinbase(client),
            _fetch_binance(client),
            return_exceptions=True,
        )
    coinbase = results[0] if isinstance(results[0], float) else None
    binance = results[1] if isinstance(results[1], float) else None

    if coinbase is not None and binance is not None:
        avg = (coinbase + binance) / 2
        divergence = abs(coinbase - binance) / avg * 100
        if divergence > MAX_DIVERGENCE_PCT:
            log.warning(
                'ETH oracle divergence %.1f%% (cb $%.2f, bn $%.2f) -- disabling ETH',
                divergence, coinbase, binance,
            )
            return None
        return EthPriceResult(price=avg, source='dual')

    log.warning(
        'ETH oracle unavailable (cb=%s, bn=%s) -- disabling ETH',
        coinbase, binance,
    )
    return None


# ---------------------------------------------------------------------------
# USD -> raw token conversion & quote builder
# ---------------------------------------------------------------------------

from pretix_eth.chains import get_token_contract


def usd_to_token_raw(usd_amount: Decimal, symbol: str, chain_id: int,
                     eth_price: Optional[float]) -> int:
    """Convert a USD amount (Decimal, e.g. 50.00) to raw token base units."""
    if symbol in ('USDC', 'USDT0'):
        contract = get_token_contract(chain_id, symbol)
        if contract is None:
            raise ValueError(f'no contract for {symbol} on chain {chain_id}')
        return int(usd_amount * (10 ** contract['decimals']))
    if symbol == 'ETH':
        if eth_price is None:
            raise ValueError('ETH conversion requires eth_price')
        eth_float = float(usd_amount) / eth_price
        return int(eth_float * 10**18)
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
BINANCE_POL_URL = 'https://api.binance.com/api/v3/ticker/price?symbol=POLUSDT'


async def _fetch_coinbase_pol(client: httpx.AsyncClient) -> float:
    r = await client.get(COINBASE_POL_URL, timeout=5.0)
    r.raise_for_status()
    return float(r.json()['data']['amount'])


async def _fetch_binance_pol(client: httpx.AsyncClient) -> float:
    r = await client.get(BINANCE_POL_URL, timeout=5.0)
    r.raise_for_status()
    return float(r.json()['price'])


async def fetch_pol_price_usd() -> Optional[EthPriceResult]:
    """Return POL price if both oracles agree within 5%. Return None if either
    oracle is unreachable or they diverge too much -- callers disable POL."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _fetch_coinbase_pol(client), _fetch_binance_pol(client),
            return_exceptions=True,
        )
    cb = results[0] if isinstance(results[0], float) else None
    bn = results[1] if isinstance(results[1], float) else None
    if cb is not None and bn is not None:
        avg = (cb + bn) / 2
        div = abs(cb - bn) / avg * 100
        if div > MAX_DIVERGENCE_PCT:
            log.warning(
                'POL oracle divergence %.1f%% (cb $%.4f, bn $%.4f) -- disabling POL',
                div, cb, bn,
            )
            return None
        return EthPriceResult(price=avg, source='dual')
    log.warning(
        'POL oracle unavailable (cb=%s, bn=%s) -- disabling POL',
        cb, bn,
    )
    return None
