# pretix_eth/x402/abi.py
"""ERC-20 and EIP-3009 ABI fragments used by the relayer."""

ERC20_ABI = [
    {
        'name': 'balanceOf',
        'type': 'function',
        'stateMutability': 'view',
        'inputs': [{'name': 'account', 'type': 'address'}],
        'outputs': [{'name': '', 'type': 'uint256'}],
    },
    {
        'name': 'decimals',
        'type': 'function',
        'stateMutability': 'view',
        'inputs': [],
        'outputs': [{'name': '', 'type': 'uint8'}],
    },
]

# EIP-3009 transferWithAuthorization — two overloads:
# 1. (from, to, value, validAfter, validBefore, nonce, v, r, s) — EOA
# 2. (from, to, value, validAfter, validBefore, nonce, signature) — ERC-1271
TRANSFER_WITH_AUTHORIZATION_EOA_ABI = {
    'name': 'transferWithAuthorization',
    'type': 'function',
    'stateMutability': 'nonpayable',
    'inputs': [
        {'name': 'from', 'type': 'address'},
        {'name': 'to', 'type': 'address'},
        {'name': 'value', 'type': 'uint256'},
        {'name': 'validAfter', 'type': 'uint256'},
        {'name': 'validBefore', 'type': 'uint256'},
        {'name': 'nonce', 'type': 'bytes32'},
        {'name': 'v', 'type': 'uint8'},
        {'name': 'r', 'type': 'bytes32'},
        {'name': 's', 'type': 'bytes32'},
    ],
    'outputs': [],
}

TRANSFER_WITH_AUTHORIZATION_BYTES_ABI = {
    'name': 'transferWithAuthorization',
    'type': 'function',
    'stateMutability': 'nonpayable',
    'inputs': [
        {'name': 'from', 'type': 'address'},
        {'name': 'to', 'type': 'address'},
        {'name': 'value', 'type': 'uint256'},
        {'name': 'validAfter', 'type': 'uint256'},
        {'name': 'validBefore', 'type': 'uint256'},
        {'name': 'nonce', 'type': 'bytes32'},
        {'name': 'signature', 'type': 'bytes'},
    ],
    'outputs': [],
}

AUTHORIZATION_STATE_ABI = {
    'name': 'authorizationState',
    'type': 'function',
    'stateMutability': 'view',
    'inputs': [
        {'name': 'authorizer', 'type': 'address'},
        {'name': 'nonce', 'type': 'bytes32'},
    ],
    'outputs': [{'name': '', 'type': 'bool'}],
}

USDC_ABI = [
    *ERC20_ABI,
    TRANSFER_WITH_AUTHORIZATION_EOA_ABI,
    TRANSFER_WITH_AUTHORIZATION_BYTES_ABI,
    AUTHORIZATION_STATE_ABI,
]
