"""Chain + token registry. Hardcoded for the 5 supported EVM chains."""
from typing import Optional

SUPPORTED_CHAINS = [1, 10, 137, 8453, 42161]

# (chain_id, token_symbol) -> {address, decimals}
# USDT0 is Tether's omnichain OFT (USD₮0) — only deployed on Optimism and Arbitrum.
# Other chains have only legacy USDT, which we do NOT accept here.
TOKEN_CONTRACTS = {
    (1, 'USDC'):      {'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'decimals': 6},
    (10, 'USDC'):     {'address': '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', 'decimals': 6},
    (10, 'USDT0'):    {'address': '0x01bFF41798a0BcF287b996046Ca68b395DbC1071', 'decimals': 6},
    (137, 'USDC'):    {'address': '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359', 'decimals': 6},
    (8453, 'USDC'):   {'address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', 'decimals': 6},
    (42161, 'USDC'):  {'address': '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', 'decimals': 6},
    (42161, 'USDT0'): {'address': '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9', 'decimals': 6},
}

CHAIN_METADATA = {
    1:     {'name': 'Ethereum', 'explorer_url': 'https://etherscan.io/tx/'},
    10:    {'name': 'Optimism', 'explorer_url': 'https://optimistic.etherscan.io/tx/'},
    137:   {'name': 'Polygon',  'explorer_url': 'https://polygonscan.com/tx/'},
    8453:  {'name': 'Base',     'explorer_url': 'https://basescan.org/tx/'},
    42161: {'name': 'Arbitrum', 'explorer_url': 'https://arbiscan.io/tx/'},
}

ALL_SYMBOLS = ('USDC', 'USDT0', 'ETH')

# Chains where the *native* currency is ETH. Polygon's native is POL, not ETH,
# so we deliberately do not offer any ETH-denominated payment there — the
# wrapped-ETH alternative (WETH as an ERC-20) is intentionally excluded too
# to keep the supported token set small and avoid double-maintenance of an
# asset that doesn't work in the x402 gasless path.
_NATIVE_ETH_CHAINS = {1, 10, 8453, 42161}


def get_token_contract(chain_id: int, symbol: str) -> Optional[dict]:
    if symbol == 'ETH':
        return None  # native, no contract
    return TOKEN_CONTRACTS.get((chain_id, symbol))


def is_supported(chain_id: int, symbol: str) -> bool:
    if chain_id not in SUPPORTED_CHAINS:
        return False
    if symbol == 'ETH':
        # Native ETH — not available on Polygon (native there is POL).
        return chain_id in _NATIVE_ETH_CHAINS
    return (chain_id, symbol) in TOKEN_CONTRACTS


# EIP-712 domain data for transferWithAuthorization (EIP-3009) signatures.
# Sourced from devcon src/types/x402.ts GaslessTokenConfig entries.
TOKEN_CONFIGS = {
    (1, 'USDC'):      {'eip712Name': 'USD Coin',  'eip712Version': '2'},
    (10, 'USDC'):     {'eip712Name': 'USD Coin',  'eip712Version': '2'},
    (10, 'USDT0'):    {'eip712Name': 'USD\u20ae0', 'eip712Version': '1'},
    (137, 'USDC'):    {'eip712Name': 'USD Coin',  'eip712Version': '2'},
    (8453, 'USDC'):   {'eip712Name': 'USD Coin',  'eip712Version': '2'},
    (42161, 'USDC'):  {'eip712Name': 'USD Coin',  'eip712Version': '2'},
    (42161, 'USDT0'): {'eip712Name': 'USD\u20ae0', 'eip712Version': '1'},
}


def get_eip712_domain(chain_id: int, symbol: str) -> Optional[dict]:
    """Return the EIP-712 domain for a stablecoin's transferWithAuthorization.
    Returns None for ETH (no EIP-3009) or unsupported chain/token combos."""
    if symbol == 'ETH':
        return None
    contract = get_token_contract(chain_id, symbol)
    config = TOKEN_CONFIGS.get((chain_id, symbol))
    if contract is None or config is None:
        return None
    return {
        'name': config['eip712Name'],
        'version': config['eip712Version'],
        'chainId': chain_id,
        'verifyingContract': contract['address'],
    }
