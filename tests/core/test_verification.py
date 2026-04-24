from unittest import mock
import pytest
from pretix_eth.verification import verify_erc20_transfer, VerificationResult

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


def _log(contract, from_addr, to_addr, value):
    def pad(a):
        return '0x' + '0' * 24 + a[2:].lower()
    return {
        'address': contract,
        'topics': [
            TRANSFER_TOPIC,
            pad(from_addr),
            pad(to_addr),
        ],
        'data': hex(value)[2:].rjust(64, '0'),
    }


def _receipt(logs, status=1, block=100):
    return {'logs': logs, 'status': status, 'blockNumber': block}


@pytest.fixture
def fake_w3():
    w3 = mock.MagicMock()
    w3.eth.block_number = 105
    return w3


def test_happy_path(fake_w3):
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, sender, recipient, 50_000_000)]
    )
    result = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_token=token, expected_amount=50_000_000,
        min_confirmations=1,
    )
    assert result.verified is True
    assert result.block_number == 100


def test_wrong_recipient_fails(fake_w3):
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    sender = '0x' + '1' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, sender, '0x' + '9' * 40, 50_000_000)]
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to='0x' + '2' * 40,
        expected_token=token, expected_amount=50_000_000, min_confirmations=1,
    )
    assert r.verified is False


def test_wrong_sender_fails(fake_w3):
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, '0x' + '9' * 40, recipient, 50_000_000)]
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to=recipient,
        expected_token=token, expected_amount=50_000_000, min_confirmations=1,
    )
    assert r.verified is False


def test_wrong_token_contract_fails(fake_w3):
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log('0x' + 'e' * 40, sender, recipient, 50_000_000)]  # scam token
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        expected_amount=50_000_000, min_confirmations=1,
    )
    assert r.verified is False


def test_insufficient_confirmations_fails(fake_w3):
    fake_w3.eth.block_number = 100
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, sender, recipient, 50_000_000)], block=100,
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_token=token, expected_amount=50_000_000,
        min_confirmations=5,
    )
    assert r.verified is False
    assert 'confirmation' in r.error.lower()


def test_tx_reverted(fake_w3):
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, sender, recipient, 50_000_000)], status=0,
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_token=token, expected_amount=50_000_000, min_confirmations=1,
    )
    assert r.verified is False
    assert 'revert' in r.error.lower() or 'failed' in r.error.lower()


def test_underpayment_fails(fake_w3):
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, sender, recipient, 49_000_000)]
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_token=token, expected_amount=50_000_000, min_confirmations=1,
    )
    assert r.verified is False


def test_overpayment_accepted(fake_w3):
    # user paid more than required — should still verify
    token = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = _receipt(
        [_log(token, sender, recipient, 60_000_000)]
    )
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_token=token, expected_amount=50_000_000, min_confirmations=1,
    )
    assert r.verified is True


def test_tx_not_mined(fake_w3):
    fake_w3.eth.get_transaction_receipt.return_value = None
    r = verify_erc20_transfer(
        w3=fake_w3, chain_id=8453, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_token='0x' + 'b' * 40, expected_amount=1, min_confirmations=1,
    )
    assert r.verified is False


def test_native_eth_happy(fake_w3):
    from pretix_eth.verification import verify_native_eth
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': sender, 'to': recipient, 'value': 10**18,
    }
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is True
    assert r.block_number == 100


def test_native_eth_wrong_recipient(fake_w3):
    from pretix_eth.verification import verify_native_eth
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': '0x' + '1' * 40, 'to': '0x' + '9' * 40, 'value': 10**18,
    }
    # Empty call tree — walker finds nothing (no_match), not trace_unavailable.
    fake_w3.provider.make_request.return_value = {'result': {'calls': []}}
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False
    assert 'mismatch' in r.error.lower()


def test_native_eth_wrong_sender(fake_w3):
    from pretix_eth.verification import verify_native_eth
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': '0x' + '9' * 40, 'to': '0x' + '2' * 40, 'value': 10**18,
    }
    fake_w3.provider.make_request.return_value = {'result': {'calls': []}}
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False
    assert 'mismatch' in r.error.lower()


def test_native_eth_trace_unavailable_is_retryable(fake_w3):
    """When debug_traceTransaction isn't supported or fails transiently, we
    return an 'RPC error' message so the frontend's retry loop kicks in —
    critical for mainnet flows where non-tracing public RPCs would otherwise
    produce a non-retryable 'mismatch' every time."""
    from pretix_eth.verification import verify_native_eth
    fake_w3.eth.get_transaction_receipt.return_value = {'status': 1, 'blockNumber': 100}
    fake_w3.eth.get_transaction.return_value = {
        'from': '0x' + '9' * 40, 'to': '0x' + '2' * 40, 'value': 10**18,
    }
    fake_w3.provider.make_request.side_effect = Exception('method not supported')
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False
    assert 'rpc error' in r.error.lower()


def test_native_eth_underpayment(fake_w3):
    from pretix_eth.verification import verify_native_eth
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': '0x' + '1' * 40, 'to': '0x' + '2' * 40, 'value': 5 * 10**17,
    }
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False


def test_native_eth_reverted(fake_w3):
    from pretix_eth.verification import verify_native_eth
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 0, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': '0x' + '1' * 40, 'to': '0x' + '2' * 40, 'value': 10**18,
    }
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False


def test_native_eth_not_mined(fake_w3):
    from pretix_eth.verification import verify_native_eth
    fake_w3.eth.get_transaction_receipt.return_value = None
    fake_w3.eth.get_transaction.return_value = None
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False
