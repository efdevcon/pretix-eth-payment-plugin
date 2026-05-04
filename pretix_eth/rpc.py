"""RPC URL resolution: env var > plugin setting > public fallback."""
import os
from typing import Optional

ALCHEMY_URL_TEMPLATES = {
    1:     'https://eth-mainnet.g.alchemy.com/v2/{key}',
    10:    'https://opt-mainnet.g.alchemy.com/v2/{key}',
    137:   'https://polygon-mainnet.g.alchemy.com/v2/{key}',
    8453:  'https://base-mainnet.g.alchemy.com/v2/{key}',
    42161: 'https://arb-mainnet.g.alchemy.com/v2/{key}',
}

PUBLIC_RPC_FALLBACKS = {
    1:     'https://ethereum.publicnode.com',
    10:    'https://optimism.publicnode.com',
    137:   'https://polygon-bor.publicnode.com',
    8453:  'https://base.publicnode.com',
    42161: 'https://arbitrum-one.publicnode.com',
}


def resolve_alchemy_key(settings_key: Optional[str]) -> Optional[str]:
    env_key = os.environ.get('WC_ALCHEMY_API_KEY')
    if env_key:
        return env_key
    if settings_key:
        return settings_key
    return None


def get_rpc_url(chain_id: int, settings_key: Optional[str]) -> str:
    if chain_id not in ALCHEMY_URL_TEMPLATES:
        raise ValueError(f'Unsupported chain_id: {chain_id}')
    key = resolve_alchemy_key(settings_key)
    if key:
        return ALCHEMY_URL_TEMPLATES[chain_id].format(key=key)
    return PUBLIC_RPC_FALLBACKS[chain_id]
