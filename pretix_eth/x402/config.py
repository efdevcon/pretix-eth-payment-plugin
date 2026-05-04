# pretix_eth/x402/config.py
"""Config resolvers: env var > plugin setting > None."""
import os
from typing import Optional


def resolve_relayer_pk(settings_value: Optional[str]) -> Optional[str]:
    env = os.environ.get('WC_RELAYER_PRIVATE_KEY')
    if env:
        return env
    return settings_value or None
