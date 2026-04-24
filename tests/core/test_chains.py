import pytest
from pretix_eth.chains import (
    SUPPORTED_CHAINS, TOKEN_CONTRACTS, CHAIN_METADATA,
    get_token_contract, is_supported,
)
from pretix_eth.chains import get_eip712_domain, TOKEN_CONFIGS


def test_all_five_chains_present():
    assert SUPPORTED_CHAINS == [1, 10, 137, 8453, 42161]


def test_base_usdc_contract():
    c = get_token_contract(8453, 'USDC')
    assert c['address'].lower() == '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
    assert c['decimals'] == 6


def test_is_supported_rejects_unknown_combo():
    assert is_supported(1, 'USDC') is True
    assert is_supported(999, 'USDC') is False
    assert is_supported(1, 'DAI') is False


def test_usdt0_only_on_optimism_and_arbitrum():
    # USD₮0 is Tether's OFT, only live on Optimism + Arbitrum.
    assert is_supported(10, 'USDT0') is True
    assert is_supported(42161, 'USDT0') is True
    # Not available elsewhere
    assert is_supported(1, 'USDT0') is False
    assert is_supported(137, 'USDT0') is False
    assert is_supported(8453, 'USDT0') is False


def test_eth_supported_only_on_native_eth_chains():
    # Native ETH — available on chains whose native currency is ETH.
    # Polygon's native is POL, not ETH; we deliberately do not offer ETH
    # (or a wrapped-ETH alternative) there to keep the supported token set
    # consistent between the wc_inject and x402 flows.
    for cid in (1, 10, 8453, 42161):
        assert is_supported(cid, 'ETH') is True
    assert is_supported(137, 'ETH') is False


def test_polygon_only_offers_usdc():
    # Polygon's supported tokens are USDC only.
    assert is_supported(137, 'USDC') is True
    assert is_supported(137, 'ETH') is False
    assert is_supported(137, 'USDT0') is False
    assert is_supported(137, 'WETH') is False


def test_chain_metadata_has_explorer_for_base():
    meta = CHAIN_METADATA[8453]
    assert 'basescan.org' in meta['explorer_url']
    assert meta['name'] == 'Base'


def test_base_usdc_domain():
    d = get_eip712_domain(8453, 'USDC')
    assert d['name'] == 'USD Coin'
    assert d['version'] == '2'
    assert d['chainId'] == 8453
    assert d['verifyingContract'].lower() == '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'


def test_optimism_usdt0_domain():
    d = get_eip712_domain(10, 'USDT0')
    assert d['name'] == 'USD\u20ae0'  # USD₮0
    assert d['version'] == '1'
    assert d['chainId'] == 10


def test_eth_has_no_domain():
    assert get_eip712_domain(8453, 'ETH') is None


def test_unsupported_combo_returns_none():
    assert get_eip712_domain(8453, 'USDT0') is None  # USDT0 not deployed on Base
