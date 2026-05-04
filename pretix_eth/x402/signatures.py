# pretix_eth/x402/signatures.py
"""Signature helpers: EOA vs smart wallet detection, ERC-6492 unwrap, EOA split."""
from eth_abi import decode

ERC6492_MAGIC = '6492649264926492649264926492649264926492649264926492649264926492'


def _strip_0x(hex_str: str) -> str:
    return hex_str[2:] if hex_str.startswith('0x') else hex_str


def is_smart_wallet_signature(signature: str) -> bool:
    """Returns True if the hex-encoded signature is longer than 65 bytes
    (the EOA EIP-712 signature size). Used to dispatch to the bytes-overload
    of USDC.transferWithAuthorization (which accepts ERC-1271 sigs)."""
    return len(_strip_0x(signature)) > 130


def split_eoa_signature(signature: str) -> dict:
    """Split a 65-byte EOA signature into v/r/s components (for the
    transferWithAuthorization(...,uint8 v,bytes32 r,bytes32 s) overload)."""
    h = _strip_0x(signature)
    if len(h) != 130:
        raise ValueError(f'Expected 65-byte signature, got {len(h) // 2} bytes')
    r = '0x' + h[0:64]
    s = '0x' + h[64:128]
    v = int(h[128:130], 16)
    if v < 27:
        v += 27  # normalize legacy 0/1 to 27/28
    return {'r': r, 's': s, 'v': v}


def unwrap_erc6492(signature: str) -> str:
    """If the signature is ERC-6492-wrapped (counterfactual smart wallet),
    decode and return the inner signature. Otherwise return as-is."""
    h = _strip_0x(signature).lower()
    if not h.endswith(ERC6492_MAGIC):
        return signature
    encoded = bytes.fromhex(h[:-len(ERC6492_MAGIC)])
    try:
        _, _, inner = decode(['address', 'bytes', 'bytes'], encoded)
    except Exception:
        return signature
    return '0x' + inner.hex()
