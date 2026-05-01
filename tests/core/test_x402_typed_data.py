# tests/core/test_x402_typed_data.py
from pretix_eth.x402.typed_data import build_transfer_authorization_typed_data


def test_build_usdc_base_typed_data():
    auth = {
        'from': '0x' + '1' * 40,
        'to': '0x' + '2' * 40,
        'value': '1000000',
        'validAfter': 0,
        'validBefore': 9_999_999_999,
        'nonce': '0x' + 'a' * 64,
    }
    td = build_transfer_authorization_typed_data(chain_id=8453, symbol='USDC', authorization=auth)
    assert td['domain']['name'] == 'USD Coin'
    assert td['domain']['version'] == '2'
    assert td['domain']['chainId'] == 8453
    assert td['domain']['verifyingContract'].lower() == '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
    assert td['primaryType'] == 'TransferWithAuthorization'
    types = td['types']
    assert 'TransferWithAuthorization' in types
    assert 'EIP712Domain' in types
    names = [f['name'] for f in types['TransferWithAuthorization']]
    assert names == ['from', 'to', 'value', 'validAfter', 'validBefore', 'nonce']
    assert td['message'] == auth


def test_unsupported_token_raises():
    import pytest
    with pytest.raises(ValueError):
        build_transfer_authorization_typed_data(chain_id=8453, symbol='USDT0', authorization={})
