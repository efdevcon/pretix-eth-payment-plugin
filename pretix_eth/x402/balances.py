"""Fetch wallet balances across chains for ETH + configured tokens.
Port of devcon src/services/x402.ts payment-options logic.

Two paths:
  - Zapper GraphQL (fast, ~200ms — single HTTP call across all chains)
  - RPC eth_calls (slow, ~2s — N chains × 2 calls each)

`fetch_balances_for_wallet` tries Zapper first when an API key is configured
and falls back to RPC on any Zapper failure (HTTP error, schema mismatch,
timeout). The RPC path remains the source of truth — Zapper is an opt-in
optimization, not a hard dependency.
"""
import logging
from typing import List, Optional
from web3 import Web3

from pretix_eth.chains import SUPPORTED_CHAINS, TOKEN_CONTRACTS
from pretix_eth.rpc import get_rpc_url
from pretix_eth.x402.abi import ERC20_ABI
from pretix_eth.x402.zapper import fetch_balances_via_zapper

log = logging.getLogger(__name__)


def _get_w3(chain_id: int, alchemy_key: Optional[str]):
    url = get_rpc_url(chain_id, settings_key=alchemy_key)
    return Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))


def fetch_balances_for_wallet(
    *, wallet: str, chain_ids: List[int], alchemy_key: Optional[str],
    zapper_api_key: Optional[str] = None,
) -> List[dict]:
    """Fast path via Zapper, with RPC as a fallback on any failure."""
    if zapper_api_key:
        zapper_entries = fetch_balances_via_zapper(
            wallet=wallet, chain_ids=chain_ids, api_key=zapper_api_key,
        )
        if zapper_entries is not None:
            return zapper_entries
        log.warning('[balances] Zapper failed, falling back to RPC for wallet=%s', wallet)
    return _fetch_balances_via_rpc(
        wallet=wallet, chain_ids=chain_ids, alchemy_key=alchemy_key,
    )


def _fetch_balances_via_rpc(
    *, wallet: str, chain_ids: List[int], alchemy_key: Optional[str],
) -> List[dict]:
    """Return a list of balance entries, one per (chain, token) combo.
    Entry shape: {chain_id, symbol, balance, decimals, token_address}.
    Silently skips chains that fail to fetch."""
    entries = []
    checksum = Web3.to_checksum_address(wallet)
    for cid in chain_ids:
        if cid not in SUPPORTED_CHAINS:
            continue
        try:
            w3 = _get_w3(cid, alchemy_key)
            # Native ETH
            eth_bal = w3.eth.get_balance(checksum)
            entries.append({
                'chain_id': cid, 'symbol': 'ETH',
                'balance': str(eth_bal), 'decimals': 18, 'token_address': None,
            })
            # Each configured token on this chain
            for (c_id, symbol), info in TOKEN_CONTRACTS.items():
                if c_id != cid:
                    continue
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(info['address']),
                    abi=ERC20_ABI,
                )
                try:
                    tok_bal = contract.functions.balanceOf(checksum).call()
                except Exception:
                    tok_bal = 0
                entries.append({
                    'chain_id': cid, 'symbol': symbol,
                    'balance': str(tok_bal), 'decimals': info['decimals'],
                    'token_address': info['address'],
                })
        except Exception:
            continue
    return entries
