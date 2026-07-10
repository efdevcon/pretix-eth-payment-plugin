from unittest import mock
import pytest
from pretix_eth.verification import verify_erc20_transfer

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


def _prestate(balances):
    """Build a prestateTracer diffMode response. `balances` maps address ->
    (pre_wei, post_wei); native-ETH verification is now a net-balance delta on
    the recipient + payer, not a tx.value / callTracer walk."""
    pre = {a: {'balance': hex(p)} for a, (p, _) in balances.items()}
    post = {a: {'balance': hex(q)} for a, (_, q) in balances.items()}
    return {'result': {'pre': pre, 'post': post}}


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


def test_overpayment_rejected(fake_w3):
    """V49: ERC-20 quotes are signed against an exact amount (USDC/USDT have
    no slippage). Overpaying mints a `Transfer` log that doesn't bind to the
    quote — accepting it lets a fat-finger send settle a future smaller
    quote. Pre-V49 code accepted any `value >= expected`; post-V49 code
    requires `value == expected`."""
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
    assert r.verified is False
    assert 'amount mismatch' in (r.error or '')


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
    # Recipient nets +1 ETH, payer nets -1 ETH (- gas): a real payment.
    fake_w3.provider.make_request.return_value = _prestate({
        sender: (2 * 10**18, 2 * 10**18 - 10**18 - 10**16),
        recipient: (0, 10**18),
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is True
    assert r.block_number == 100


def test_native_eth_wrong_recipient(fake_w3):
    from pretix_eth.verification import verify_native_eth
    sender = '0x' + '1' * 40
    other = '0x' + '9' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': sender, 'to': other, 'value': 10**18,
    }
    # The ETH went to `other`, so the EXPECTED recipient (0x2222) nets 0.
    fake_w3.provider.make_request.return_value = _prestate({
        sender: (2 * 10**18, 2 * 10**18 - 10**18 - 10**16),
        other: (0, 10**18),
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to='0x' + '2' * 40,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False
    assert 'net' in r.error.lower()


def test_native_eth_wrong_sender(fake_w3):
    from pretix_eth.verification import verify_native_eth
    recipient = '0x' + '2' * 40
    other = '0x' + '9' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': other, 'to': recipient, 'value': 10**18,
    }
    # `other` paid, so the EXPECTED payer (0x1111) nets 0 — the payer-debit
    # clause rejects even though the recipient was credited.
    fake_w3.provider.make_request.return_value = _prestate({
        other: (2 * 10**18, 2 * 10**18 - 10**18 - 10**16),
        recipient: (0, 10**18),
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from='0x' + '1' * 40, expected_to=recipient,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False
    assert 'net' in r.error.lower()


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
    sender = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {
        'status': 1, 'blockNumber': 100,
    }
    fake_w3.eth.get_transaction.return_value = {
        'from': sender, 'to': recipient, 'value': 5 * 10**17,
    }
    # Recipient nets only 0.5 ETH, below the slippage-adjusted 1 ETH minimum.
    fake_w3.provider.make_request.return_value = _prestate({
        sender: (2 * 10**18, 2 * 10**18 - 5 * 10**17 - 10**16),
        recipient: (0, 5 * 10**17),
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=sender, expected_to=recipient,
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


# ---------------------------------------------------------------------------
# Wallet-shape coverage (Tier-1 CI): verify_native_eth + verify_eth_payer_signature
# across EOA / ERC-4337 smart wallet / Safe / EIP-7702, mocking the RPC so these
# run in plain pytest with no devnet. Guards the two launch mitigations (net-
# balance oracle for contract payers, ERC-1271 gas cap) + the V77 refusal.
# ---------------------------------------------------------------------------

def test_native_eth_smart_wallet_bundler(fake_w3):
    """ERC-4337: the outer tx.from is a bundler EOA, but it's the smart-wallet
    payer's balance that must net the debit. The oracle keys off expected_from
    (the wallet), not tx.from, so bundler-relayed payments verify."""
    from pretix_eth.verification import verify_native_eth
    wallet = '0x' + 'a' * 40
    recipient = '0x' + 'b' * 40
    bundler = '0x' + 'c' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {'status': 1, 'blockNumber': 100}
    fake_w3.eth.get_transaction.return_value = {'from': bundler, 'to': wallet, 'value': 0}
    fake_w3.provider.make_request.return_value = _prestate({
        wallet: (2 * 10**18, 10**18),           # wallet paid 1 ETH
        recipient: (0, 10**18),                 # recipient netted 1 ETH
        bundler: (10**18, 10**18 - 10**16),     # bundler only paid gas
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=wallet, expected_to=recipient,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is True


def test_native_eth_safe_with_gas_refund(fake_w3):
    """A Safe execTransaction can debit the Safe by value + an owner gas refund;
    a larger debit still satisfies the payer-debit clause, so it verifies."""
    from pretix_eth.verification import verify_native_eth
    safe = '0x' + 'd' * 40
    recipient = '0x' + 'e' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {'status': 1, 'blockNumber': 100}
    fake_w3.eth.get_transaction.return_value = {'from': '0x' + 'f' * 40, 'to': safe, 'value': 0}
    fake_w3.provider.make_request.return_value = _prestate({
        safe: (3 * 10**18, 3 * 10**18 - 10**18 - 2 * 10**16),  # value + gas refund
        recipient: (0, 10**18),
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=safe, expected_to=recipient,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is True


def test_native_eth_pay_then_forward_rejected(fake_w3):
    """Phantom class (v74): the recipient is credited then forwards the ETH out
    in the same tx, netting 0. Must be rejected even though nothing reverts."""
    from pretix_eth.verification import verify_native_eth
    payer = '0x' + '1' * 40
    recipient = '0x' + '2' * 40
    sink = '0x' + '7' * 40
    fake_w3.eth.get_transaction_receipt.return_value = {'status': 1, 'blockNumber': 100}
    fake_w3.eth.get_transaction.return_value = {'from': payer, 'to': recipient, 'value': 10**18}
    fake_w3.provider.make_request.return_value = _prestate({
        payer: (2 * 10**18, 2 * 10**18 - 10**18 - 10**16),
        recipient: (0, 0),        # credited then forwarded out -> net 0
        sink: (0, 10**18),
    })
    r = verify_native_eth(
        w3=fake_w3, tx_hash='0x' + 'a' * 64,
        expected_from=payer, expected_to=recipient,
        expected_amount_wei=10**18, min_confirmations=1,
    )
    assert r.verified is False


def test_sig_eoa_ecdsa_roundtrip():
    """Plain EOA: a real personal_sign recovers to the payer -> valid (no RPC)."""
    from eth_account import Account
    from eth_account.messages import encode_defunct
    from pretix_eth.verification import verify_eth_payer_signature
    acct = Account.create()
    msg = 'Devcon ticket payment'
    sig = Account.sign_message(encode_defunct(text=msg), acct.key).signature.hex()
    if not sig.startswith('0x'):
        sig = '0x' + sig
    assert verify_eth_payer_signature(
        w3=mock.MagicMock(), payer=acct.address, message=msg, signature=sig,
    ) is True


def test_sig_safe_static_part_refused():
    """V77: a 65-byte {r=owner, s=0, v=1} Safe approveHash static part carries no
    ECDSA material and is refused BEFORE any ERC-1271 eth_call."""
    from pretix_eth.verification import verify_eth_payer_signature
    owner = '3' * 40
    sig = '0x' + owner.rjust(64, '0') + '00' * 32 + '01'  # r=owner, s=0, v=1
    w3 = mock.MagicMock()
    assert verify_eth_payer_signature(
        w3=w3, payer='0x' + '4' * 40, message='m', signature=sig,
    ) is False
    w3.eth.call.assert_not_called()


def test_sig_erc1271_gas_capped():
    """Coinbase Smart Wallet / Safe ERC-1271 validators are eth_call'd with a
    bounded gas cap (hostile-validator DoS guard) that is nonetheless high
    enough for on-chain P256/passkey verification."""
    from pretix_eth.verification import (
        verify_eth_payer_signature, ISVALIDSIG_GAS_CAP, ERC1271_MAGIC,
    )
    assert ISVALIDSIG_GAS_CAP >= 1_000_000
    w3 = mock.MagicMock()
    w3.eth.get_code.return_value = bytes.fromhex('6080604052')  # non-empty, not 7702
    calls = []

    def _call(tx, *a, **k):
        calls.append(tx)
        # zero-sig probe (#1) non-magic; real ERC-1271 call (#2) magic
        return ERC1271_MAGIC if len(calls) > 1 else b'\x00' * 32
    w3.eth.call.side_effect = _call
    ok = verify_eth_payer_signature(
        w3=w3, payer='0x' + '5' * 40, message='m', signature='0x' + 'ab' * 100,
    )
    assert ok is True
    assert calls and all(c.get('gas') == ISVALIDSIG_GAS_CAP for c in calls)


def test_sig_7702_delegated_still_supported():
    """A legit EIP-7702-delegated EOA (0xef0100||impl) validates via its delegate's
    ERC-1271. We did NOT blanket-refuse 0xef0100, so 7702 wallets keep working."""
    from pretix_eth.verification import (
        verify_eth_payer_signature, EIP7702_PREFIX, ERC1271_MAGIC,
    )
    w3 = mock.MagicMock()
    w3.eth.get_code.return_value = EIP7702_PREFIX + bytes.fromhex('9' * 40)  # 23 bytes
    calls = []

    def _call(tx, *a, **k):
        calls.append(tx)
        return ERC1271_MAGIC if len(calls) > 1 else b'\x00' * 32
    w3.eth.call.side_effect = _call
    assert verify_eth_payer_signature(
        w3=w3, payer='0x' + '6' * 40, message='m', signature='0x' + 'cd' * 80,
    ) is True
