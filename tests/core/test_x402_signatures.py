# tests/core/test_x402_signatures.py
from pretix_eth.x402.signatures import is_smart_wallet_signature, split_eoa_signature, unwrap_erc6492


def test_eoa_signature_65_bytes():
    sig = '0x' + 'a' * 130  # 65 bytes = 130 hex chars
    assert is_smart_wallet_signature(sig) is False


def test_smart_wallet_signature_longer_than_65_bytes():
    sig = '0x' + 'a' * 200
    assert is_smart_wallet_signature(sig) is True


def test_split_eoa_signature():
    # 65 bytes: r (32) + s (32) + v (1)
    sig = '0x' + 'a' * 64 + 'b' * 64 + '1c'  # r=aa..., s=bb..., v=0x1c (28)
    parts = split_eoa_signature(sig)
    assert parts['r'] == '0x' + 'a' * 64
    assert parts['s'] == '0x' + 'b' * 64
    assert parts['v'] == 28


def test_unwrap_erc6492_not_wrapped():
    """A signature without the 6492 magic suffix returns as-is."""
    sig = '0x' + 'a' * 130
    assert unwrap_erc6492(sig) == sig


def test_unwrap_erc6492_wrapped():
    """A 6492-wrapped signature returns the inner signature."""
    # ERC-6492: abi.encode(factory, factoryCalldata, signature) || MAGIC_BYTES
    # MAGIC_BYTES = 0x6492649264926492649264926492649264926492649264926492649264926492
    from eth_abi import encode
    inner_sig = bytes.fromhex('a' * 130)
    factory = bytes.fromhex('b' * 40)
    factory_calldata = b'\x00' * 32
    encoded = encode(['address', 'bytes', 'bytes'], [factory, factory_calldata, inner_sig])
    magic = bytes.fromhex('6492' * 16)
    wrapped = '0x' + (encoded + magic).hex()
    assert unwrap_erc6492(wrapped) == '0x' + inner_sig.hex()
