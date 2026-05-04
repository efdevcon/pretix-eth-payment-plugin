# pretix_eth/x402/typed_data.py
"""EIP-712 typed data for EIP-3009 transferWithAuthorization."""
from pretix_eth.chains import get_eip712_domain

TRANSFER_AUTHORIZATION_TYPES = {
    'EIP712Domain': [
        {'name': 'name', 'type': 'string'},
        {'name': 'version', 'type': 'string'},
        {'name': 'chainId', 'type': 'uint256'},
        {'name': 'verifyingContract', 'type': 'address'},
    ],
    'TransferWithAuthorization': [
        {'name': 'from', 'type': 'address'},
        {'name': 'to', 'type': 'address'},
        {'name': 'value', 'type': 'uint256'},
        {'name': 'validAfter', 'type': 'uint256'},
        {'name': 'validBefore', 'type': 'uint256'},
        {'name': 'nonce', 'type': 'bytes32'},
    ],
}


def build_transfer_authorization_typed_data(*, chain_id: int, symbol: str, authorization: dict) -> dict:
    domain = get_eip712_domain(chain_id, symbol)
    if domain is None:
        raise ValueError(f'No EIP-712 domain for {symbol} on chain {chain_id}')
    return {
        'domain': domain,
        'types': TRANSFER_AUTHORIZATION_TYPES,
        'primaryType': 'TransferWithAuthorization',
        'message': authorization,
    }
