"""Fetch wallet balances via Zapper's public GraphQL API.

Used as the *fast* path for /plugin/x402/payment-options/ — Zapper handles
the multi-chain fan-out + token enrichment in a single HTTP call (~200ms),
versus ~2s of sequential RPC eth_calls per chain.

Returns the same entry shape as `balances.fetch_balances_for_wallet` so the
caller can swap implementations without changes.

Returns None on any failure (missing API key, HTTP error, schema mismatch,
timeout) — caller is expected to fall back to the RPC path.
"""
import json
import logging
from typing import List, Optional
from urllib import request as urlrequest, error as urlerror

from pretix_eth.chains import SUPPORTED_CHAINS, TOKEN_CONTRACTS

log = logging.getLogger(__name__)

ZAPPER_GRAPHQL = 'https://public.zapper.xyz/graphql'

# Zapper's public.zapper.xyz/graphql shape (late 2025+). If the schema
# changes again, the HTTP 400 body (logged on failure) will tell us what's
# wrong; bump this query then.
_QUERY = """
query Balances($addresses: [Address!]!, $networks: [Network!]) {
  portfolio(addresses: $addresses, networks: $networks) {
    tokenBalances {
      address
      network
      token {
        balanceRaw
        baseToken {
          address
          symbol
        }
      }
    }
  }
}
"""

_CHAIN_ID_TO_NETWORK = {
    1: 'ETHEREUM_MAINNET',
    10: 'OPTIMISM_MAINNET',
    137: 'POLYGON_MAINNET',
    8453: 'BASE_MAINNET',
    42161: 'ARBITRUM_MAINNET',
}
_NETWORK_TO_CHAIN_ID = {v: k for k, v in _CHAIN_ID_TO_NETWORK.items()}

_ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'


def _build_token_lookup(chain_ids):
    """Map (chain_id, lower(token_address)) -> (symbol, decimals) for fast match."""
    lut = {}
    for (cid, symbol), info in TOKEN_CONTRACTS.items():
        if cid in chain_ids:
            lut[(cid, info['address'].lower())] = (symbol, info['decimals'])
    return lut


def fetch_balances_via_zapper(
    *, wallet: str, chain_ids: List[int], api_key: Optional[str],
    timeout_s: float = 4.0,
) -> Optional[List[dict]]:
    """Fetch wallet balances via Zapper's GraphQL portfolio query.

    Returns a list shaped like `balances.fetch_balances_for_wallet` (dicts
    with chain_id/symbol/balance/decimals/token_address) — limited to the
    chains/tokens *we* support. Zapper-side tokens we don't recognize are
    dropped silently.

    Returns None on any failure path so the caller can fall back to RPC.
    """
    if not api_key:
        return None

    chain_ids = [c for c in chain_ids if c in SUPPORTED_CHAINS]
    networks = [_CHAIN_ID_TO_NETWORK[c] for c in chain_ids if c in _CHAIN_ID_TO_NETWORK]
    if not networks:
        return None

    payload = json.dumps({
        'query': _QUERY,
        'variables': {'addresses': [wallet], 'networks': networks},
    }).encode('utf-8')

    req = urlrequest.Request(
        ZAPPER_GRAPHQL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'x-zapper-api-key': api_key,
            # Cloudflare in front of public.zapper.xyz blocks the default
            # `Python-urllib/x.y` UA with HTTP 403 "error code: 1010" (banned
            # browser signature). Send a generic UA so the request isn't
            # treated as a bot. The actual UA string just needs to look real;
            # Cloudflare doesn't validate it semantically.
            'User-Agent': 'pretix-eth-plugin/1.0 (+https://pretix.eu)',
            'Accept': 'application/json',
        },
        method='POST',
    )

    try:
        with urlrequest.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except urlerror.HTTPError as e:
        # Zapper returns GraphQL errors as 400 with a useful body — surface it.
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:500]
        except Exception:
            pass
        log.warning('[zapper] HTTP %s body=%s', e.code, body)
        return None
    except (urlerror.URLError, TimeoutError, OSError) as e:
        log.warning('[zapper] request failed: %s', e)
        return None

    try:
        body = json.loads(raw)
    except ValueError:
        log.warning('[zapper] non-JSON response')
        return None

    if body.get('errors'):
        log.warning('[zapper] GraphQL errors: %s', body['errors'])
        return None

    balances = (body.get('data') or {}).get('portfolio') or {}
    token_balances = balances.get('tokenBalances') or []

    token_lut = _build_token_lookup(set(chain_ids))

    # Track which (chain, symbol) entries we've already produced so we can
    # backfill zeros for missing combinations afterward.
    seen = set()
    entries = []

    for tb in token_balances:
        cid = _NETWORK_TO_CHAIN_ID.get(tb.get('network') or '')
        if cid not in chain_ids:
            continue
        token = tb.get('token') or {}
        base = token.get('baseToken') or {}
        addr = (base.get('address') or '').lower()
        balance_raw = token.get('balanceRaw')
        if balance_raw is None:
            continue
        # Zapper returns balanceRaw as a string of base units already.
        balance_str = str(balance_raw)

        if addr == _ZERO_ADDRESS or addr == '':
            entries.append({
                'chain_id': cid, 'symbol': 'ETH',
                'balance': balance_str, 'decimals': 18, 'token_address': None,
            })
            seen.add((cid, 'ETH'))
            continue

        match = token_lut.get((cid, addr))
        if not match:
            continue  # Unsupported token on this chain — ignore.
        symbol, decimals = match
        entries.append({
            'chain_id': cid, 'symbol': symbol,
            'balance': balance_str, 'decimals': decimals, 'token_address': addr,
        })
        seen.add((cid, symbol))

    # Backfill zero entries for any (chain, supported_symbol) the caller
    # asked about but Zapper omitted (Zapper drops zero-balance positions).
    # Without this, the payment-options endpoint loses rows the UI expects.
    for cid in chain_ids:
        if (cid, 'ETH') not in seen:
            entries.append({
                'chain_id': cid, 'symbol': 'ETH',
                'balance': '0', 'decimals': 18, 'token_address': None,
            })
        for (c_id, symbol), info in TOKEN_CONTRACTS.items():
            if c_id != cid:
                continue
            if (cid, symbol) not in seen:
                entries.append({
                    'chain_id': cid, 'symbol': symbol,
                    'balance': '0', 'decimals': info['decimals'],
                    'token_address': info['address'],
                })

    return entries
