# tests/core/test_x402_relayer.py
from unittest import mock
import pytest
from pretix_eth.x402.relayer import (
    execute_transfer_with_authorization, RelayerResult, RelayerError,
)


@pytest.fixture
def fake_w3():
    w3 = mock.MagicMock()
    w3.eth.gas_price = 10**8  # 0.1 gwei, under Base cap 0.13
    w3.eth.get_balance.return_value = 10**18
    w3.eth.get_transaction_count.return_value = 42
    # authorizationState returns False (nonce unused)
    contract_mock = mock.MagicMock()
    contract_mock.functions.authorizationState.return_value.call.return_value = False
    contract_mock.functions.balanceOf.return_value.call.return_value = 10**9  # 1000 USDC
    # build_transaction returns dict
    contract_mock.functions.transferWithAuthorization.return_value.build_transaction.return_value = {
        'to': '0xtoken', 'data': '0x01', 'gas': 100000, 'gasPrice': 10**8, 'nonce': 42,
        'chainId': 8453, 'from': '0xrelayer',
    }
    w3.eth.contract.return_value = contract_mock
    # send_raw_transaction returns a hash
    w3.eth.send_raw_transaction.return_value = bytes.fromhex('cd' * 32)
    return w3


@pytest.fixture
def fake_account():
    acct = mock.MagicMock()
    acct.address = '0x' + '1' * 40
    signed = mock.MagicMock()
    signed.rawTransaction = b'\xaa' * 100
    signed.raw_transaction = signed.rawTransaction  # eth-account v0.13+ uses snake_case
    acct.sign_transaction.return_value = signed
    return acct


def test_execute_eoa_signature(fake_w3, fake_account, monkeypatch):
    monkeypatch.setattr(
        'pretix_eth.x402.relayer._get_w3',
        lambda chain_id, settings_key: fake_w3,
    )
    monkeypatch.setattr(
        'pretix_eth.x402.relayer._get_relayer_account',
        lambda pk: fake_account,
    )
    auth = {
        'from': '0x' + '2' * 40,
        'to': '0x' + '3' * 40,
        'value': '1000000',
        'validAfter': 0,
        'validBefore': 9_999_999_999,
        'nonce': '0x' + 'a' * 64,
    }
    # 65-byte EOA signature
    sig = '0x' + 'a' * 64 + 'b' * 64 + '1c'
    result = execute_transfer_with_authorization(
        chain_id=8453, symbol='USDC', authorization=auth,
        signature=sig, relayer_pk='0xdeadbeef', alchemy_key=None,
    )
    assert isinstance(result, RelayerResult)
    assert result.tx_hash == '0x' + 'cd' * 32


def test_execute_rejects_if_nonce_already_used(fake_w3, fake_account, monkeypatch):
    monkeypatch.setattr(
        'pretix_eth.x402.relayer._get_w3',
        lambda chain_id, settings_key: fake_w3,
    )
    monkeypatch.setattr(
        'pretix_eth.x402.relayer._get_relayer_account',
        lambda pk: fake_account,
    )
    # Flip authorizationState to True
    fake_w3.eth.contract.return_value.functions.authorizationState.return_value.call.return_value = True
    auth = {
        'from': '0x' + '2' * 40, 'to': '0x' + '3' * 40, 'value': '1000',
        'validAfter': 0, 'validBefore': 9_999_999_999,
        'nonce': '0x' + 'a' * 64,
    }
    with pytest.raises(RelayerError, match='nonce already used'):
        execute_transfer_with_authorization(
            chain_id=8453, symbol='USDC', authorization=auth,
            signature='0x' + 'a' * 130, relayer_pk='0xdeadbeef', alchemy_key=None,
        )


def test_execute_rejects_if_insufficient_balance(fake_w3, fake_account, monkeypatch):
    monkeypatch.setattr(
        'pretix_eth.x402.relayer._get_w3',
        lambda chain_id, settings_key: fake_w3,
    )
    monkeypatch.setattr(
        'pretix_eth.x402.relayer._get_relayer_account',
        lambda pk: fake_account,
    )
    fake_w3.eth.contract.return_value.functions.balanceOf.return_value.call.return_value = 0
    auth = {
        'from': '0x' + '2' * 40, 'to': '0x' + '3' * 40, 'value': '1000000',
        'validAfter': 0, 'validBefore': 9_999_999_999,
        'nonce': '0x' + 'a' * 64,
    }
    with pytest.raises(RelayerError, match='insufficient'):
        execute_transfer_with_authorization(
            chain_id=8453, symbol='USDC', authorization=auth,
            signature='0x' + 'a' * 130, relayer_pk='0xdeadbeef', alchemy_key=None,
        )
