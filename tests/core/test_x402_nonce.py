# tests/core/test_x402_nonce.py
from pretix_eth.x402.nonce import generate_nonce_bytes32


def test_nonce_is_32_bytes_hex():
    n = generate_nonce_bytes32()
    assert n.startswith('0x')
    assert len(n) == 66  # 0x + 64 hex chars


def test_nonces_are_unique():
    nonces = {generate_nonce_bytes32() for _ in range(100)}
    assert len(nonces) == 100
