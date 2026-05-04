# pretix_eth/x402/nonce.py
"""Random bytes32 nonce for EIP-3009 authorizations."""
import secrets


def generate_nonce_bytes32() -> str:
    return '0x' + secrets.token_hex(32)
