"""On-chain verification for ERC-20 Transfer and native ETH sends."""
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# keccak256("Transfer(address,address,uint256)")
ERC20_TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


@dataclass
class VerificationResult:
    verified: bool
    block_number: Optional[int] = None
    confirmed_at: Optional[int] = None
    error: Optional[str] = None


def _normalize_hex(val) -> str:
    """Convert HexBytes / bytes / str to a lowercase 0x-prefixed hex string."""
    if hasattr(val, 'hex'):
        val = val.hex()
    s = str(val).lower()
    if not s.startswith('0x'):
        s = '0x' + s
    return s


def _addr_eq(a, b) -> bool:
    return _normalize_hex(a) == _normalize_hex(b)


def _topic_to_addr(topic) -> str:
    # 32-byte topic → last 20 bytes as 0x-prefixed hex
    h = _normalize_hex(topic)  # '0x' + 64 hex chars
    return '0x' + h[-40:]


def verify_erc20_transfer(*, w3, chain_id: int, tx_hash: str,
                          expected_from: str, expected_to: str,
                          expected_token: str, expected_amount: int,
                          min_confirmations: int = 1) -> VerificationResult:
    # Defense-in-depth: reject zero or negative expected amounts to prevent
    # any upstream bug from producing a trivially-satisfiable verification.
    if expected_amount <= 0:
        return VerificationResult(False, error=f'invalid expected_amount: {expected_amount}')

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        return VerificationResult(False, error=f'RPC error: {e}')

    if receipt is None:
        return VerificationResult(False, error='tx not mined yet')

    if receipt.get('status') != 1:
        return VerificationResult(False, error='tx reverted on-chain')

    block = receipt.get('blockNumber')
    head = w3.eth.block_number
    if head - block < min_confirmations:
        return VerificationResult(
            False, error=f'insufficient confirmations ({head - block}/{min_confirmations})',
        )

    # Find matching Transfer log
    for log_entry in receipt.get('logs', []):
        if not _addr_eq(log_entry.get('address', ''), expected_token):
            continue
        topics = log_entry.get('topics', [])
        if len(topics) < 3:
            continue
        if _normalize_hex(topics[0]) != ERC20_TRANSFER_TOPIC:
            continue
        t_from = _topic_to_addr(topics[1])
        t_to = _topic_to_addr(topics[2])
        if not _addr_eq(t_from, expected_from):
            continue
        if not _addr_eq(t_to, expected_to):
            continue
        data_hex = _normalize_hex(log_entry.get('data', '0x0'))[2:]  # strip 0x
        value = int(data_hex, 16) if data_hex else 0
        if value < expected_amount:
            return VerificationResult(False, error=f'amount too low: {value} < {expected_amount}')
        return VerificationResult(True, block_number=block)

    return VerificationResult(False, error='no matching transfer found in tx')


def _find_internal_eth_transfer(w3, tx_hash: str, from_lower: str,
                                to_lower: str, min_value: int) -> str:
    """Walk debug_traceTransaction call tree looking for an internal ETH
    transfer from `from_lower` to `to_lower` with value >= `min_value`.
    Supports ERC-4337 bundler flows (e.g. Coinbase Smart Wallet + paymaster)
    where the outer tx.from is a bundler EOA. Requires Alchemy or enterprise RPC.

    Returns one of: 'match' | 'no_match' | 'trace_unavailable' — so callers can
    distinguish "RPC doesn't support tracing" from "RPC traced and found nothing",
    which matters for error classification (the first is transient-ish; the
    second is a real verification failure)."""
    try:
        trace = w3.provider.make_request('debug_traceTransaction', [tx_hash, {'tracer': 'callTracer'}])
    except Exception as e:
        log.warning('debug_traceTransaction request failed for %s: %s', tx_hash, e)
        return 'trace_unavailable'
    if not isinstance(trace, dict):
        return 'trace_unavailable'
    if trace.get('error'):
        log.warning('debug_traceTransaction returned error for %s: %s', tx_hash, trace.get('error'))
        return 'trace_unavailable'
    result = trace.get('result')
    if not isinstance(result, dict):
        return 'trace_unavailable'
    try:
        stack = [result]
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            val_hex = node.get('value', '0x0')
            try:
                node_value = int(val_hex, 16) if isinstance(val_hex, str) else int(val_hex)
            except (TypeError, ValueError):
                node_value = 0
            if (node_value >= min_value
                    and _normalize_hex(node.get('from', '')).lower() == from_lower
                    and _normalize_hex(node.get('to', '')).lower() == to_lower):
                return 'match'
            calls = node.get('calls')
            if isinstance(calls, list):
                stack.extend(calls)
        return 'no_match'
    except Exception as e:
        log.warning('debug_traceTransaction walk failed for %s: %s', tx_hash, e)
        return 'trace_unavailable'


SLIPPAGE_BPS = 50  # 0.50%

def _min_acceptable_wei(expected_wei: int) -> int:
    """How much ETH we'll accept as 'paid in full' for an `expected_wei` quote.
    Allows for two real-world drift sources:
      - ETH spot price moves between our oracle fetch and the wallet's signing
      - Smart-account wallets (notably MetaMask 7702 mode) re-derive `value`
        at signing time using their own price feed instead of passing through
        our exact wei amount
    Industry-standard 0.5% (50 bps) — same as Uniswap's default — comfortably
    absorbs both. The merchant's worst case loss per order at this bound is
    half a percent of the order's USD total."""
    return expected_wei - (expected_wei * SLIPPAGE_BPS) // 10_000


def verify_native_eth(*, w3, tx_hash: str, expected_from: str,
                      expected_to: str, expected_amount_wei: int,
                      min_confirmations: int = 1) -> VerificationResult:
    # Defense-in-depth: reject zero or negative expected amounts.
    if expected_amount_wei <= 0:
        return VerificationResult(False, error=f'invalid expected_amount_wei: {expected_amount_wei}')

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        tx = w3.eth.get_transaction(tx_hash)
    except Exception as e:
        return VerificationResult(False, error=f'RPC error: {e}')

    if receipt is None or tx is None:
        return VerificationResult(False, error='tx not mined yet')

    if receipt.get('status') != 1:
        return VerificationResult(False, error='tx reverted on-chain')

    block = receipt.get('blockNumber')
    head = w3.eth.block_number
    if head - block < min_confirmations:
        return VerificationResult(
            False, error=f'insufficient confirmations ({head - block}/{min_confirmations})',
        )

    min_wei = _min_acceptable_wei(expected_amount_wei)

    # Happy path: EOA direct send
    from_match = _addr_eq(tx.get('from', ''), expected_from)
    to_match = _addr_eq(tx.get('to', ''), expected_to)
    if from_match and to_match:
        actual = int(tx.get('value', 0))
        if actual < min_wei:
            return VerificationResult(
                False,
                error=f'tx value too low: {actual} < {min_wei} '
                      f'(expected ≥{min_wei}, quote was {expected_amount_wei}, slippage tolerance {SLIPPAGE_BPS / 100:.2f}%)',
            )
        return VerificationResult(True, block_number=block)

    # Smart wallet / ERC-4337 fallback: trace internal calls. Use the same
    # slippage-adjusted minimum so we don't reject 7702/UserOp transfers that
    # underpay the quote by tiny amounts due to wallet-side re-quoting.
    from_lower = _normalize_hex(expected_from).lower()
    to_lower = _normalize_hex(expected_to).lower()
    trace_outcome = _find_internal_eth_transfer(
        w3, tx_hash, from_lower, to_lower, min_wei,
    )
    if trace_outcome == 'match':
        return VerificationResult(True, block_number=block)
    if trace_outcome == 'trace_unavailable':
        # RPC didn't give us a usable trace — could be a transient indexer
        # lag or the RPC provider doesn't support debug_*. Returning an
        # "rpc error" message makes the frontend auto-retry. If it's really
        # unsupported, the retries will all produce the same result and
        # eventually surface to the user.
        return VerificationResult(
            False,
            error=f'RPC error: debug_traceTransaction unavailable for {tx_hash}; '
                  f'tx.from={tx.get("from")} does not match expected_from={expected_from}',
        )

    return VerificationResult(
        False,
        error=f'tx from/to mismatch: tx.from={tx.get("from")}, tx.to={tx.get("to")} '
              f'(expected from={expected_from} to={expected_to}); no matching internal transfer found',
    )


def build_eth_payer_message(payment_reference: str, payer: str, chain_id: int) -> str:
    """Build the human-readable message the ETH payer signs to prove wallet ownership."""
    return (
        'Devcon ticket payment (ETH)\n'
        f'Payment reference: {payment_reference}\n'
        f'Payer: {payer}\n'
        f'Chain: {chain_id}'
    )


ERC1271_MAGIC = bytes.fromhex('1626ba7e')
ERC6492_MAGIC_SUFFIX = bytes.fromhex(
    '6492649264926492649264926492649264926492649264926492649264926492',
)
# EIP-7702 designator: a delegated EOA's `eth_getCode` returns
# `0xef0100 || <delegated_implementation_address>` (3 + 20 = 23 bytes).
EIP7702_PREFIX = bytes.fromhex('ef0100')

# `bytes4(keccak256("DOMAIN_SEPARATOR()"))` — most OpenZeppelin / EIP-712-based
# contracts expose this view; we use it to discover the contract's chain-bound
# hash envelope without having to know the implementation type.
DOMAIN_SEPARATOR_SELECTOR = bytes.fromhex('3644e515')


def _try_erc1271(w3, payer_cs: str, hash_to_check: bytes, sig_bytes: bytes) -> Optional[bytes]:
    """Call isValidSignature(bytes32, bytes) on `payer_cs`. Returns the magic
    bytes (or whatever the contract returned) on success, or None if the call
    reverted / returned garbage."""
    from eth_abi import encode as abi_encode
    selector = bytes.fromhex('1626ba7e')
    try:
        encoded_args = abi_encode(['bytes32', 'bytes'], [hash_to_check, sig_bytes])
        calldata = '0x' + (selector + encoded_args).hex()
        result = w3.eth.call({'to': payer_cs, 'data': calldata})
    except Exception as e:
        log.warning(
            'eth_payer_signature: isValidSignature eth_call reverted on %s: %s',
            payer_cs, e,
        )
        return None
    if isinstance(result, (bytes, bytearray)):
        return bytes(result[:4])
    try:
        return bytes.fromhex(result.hex()[:8])
    except Exception:
        return None


def _try_fetch_domain_separator(w3, payer_cs: str) -> Optional[bytes]:
    """Read `DOMAIN_SEPARATOR()` (ERC-1967/EIP-712 convention) from the wallet
    contract. Used as the chain-bound envelope when the wallet is a 7702-style
    smart account that expects ERC-7739-flavored signatures.

    Returns the 32-byte separator or None if the call reverts / the contract
    doesn't expose it."""
    try:
        result = w3.eth.call({
            'to': payer_cs, 'data': '0x' + DOMAIN_SEPARATOR_SELECTOR.hex(),
        })
    except Exception as e:
        log.debug(
            'eth_payer_signature: DOMAIN_SEPARATOR() probe failed on %s: %s',
            payer_cs, e,
        )
        return None
    if isinstance(result, (bytes, bytearray)) and len(result) >= 32:
        return bytes(result[:32])
    return None


def verify_eth_payer_signature(*, w3, payer: str, message: str, signature: str) -> bool:
    """Verify an EIP-191 personal_sign signature against `payer`.

    Handles three signature modes:
      1. EOA (65 bytes): local ECDSA recovery, compare to payer.
      2. ERC-1271 (variable length, smart wallet already deployed): eth_call
         `isValidSignature(hash, signature)` on the payer contract.
      3. ERC-6492 (signature suffixed with magic bytes, counterfactual wallet):
         unwrap to `(factory, factoryCalldata, innerSig)` and for now just
         verify `innerSig` via ERC-1271. If the wallet isn't deployed yet on
         this chain the eth_call returns empty bytes; we fall through to
         failure (proper 6492 handling via UniversalSigValidator is TODO).

    Logs a warning on every failure path so production can diagnose without
    having to reproduce locally."""
    from eth_account import Account
    from eth_account.messages import encode_defunct
    from eth_abi import decode as abi_decode
    from web3 import Web3

    # 1) EOA ECDSA recovery — fast, no RPC.
    recovered = None
    try:
        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=signature)
        if _addr_eq(recovered, payer):
            return True
    except Exception as e:
        log.debug('eth_payer_signature: ECDSA recovery skipped (%s)', e)
    # If recovery succeeded but to a *different* address, that's diagnostic
    # gold — Frame's "MetaMask compatibility" mode and some 7702 setups can
    # produce signatures that recover to an unrelated key. Surface it instead
    # of silently falling through to ERC-1271 (which then reports the
    # confusing "no contract code on this chain" error).
    if recovered and not _addr_eq(recovered, payer):
        log.warning(
            'eth_payer_signature: ECDSA recovered %s but expected payer=%s '
            '(falling through to ERC-1271)',
            recovered, payer,
        )

    # Normalize sig bytes
    try:
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith('0x') else signature)
    except Exception as e:
        log.warning('eth_payer_signature: invalid hex signature: %s', e)
        return False

    # Unwrap ERC-6492 (counterfactual wallets) if present. If the suffix
    # matches, the payload is ABI-encoded (factory, factoryCalldata, innerSig).
    # We pull out innerSig and try ERC-1271 with that; if the wallet isn't
    # deployed on this chain, the eth_call will fail cleanly.
    if sig_bytes.endswith(ERC6492_MAGIC_SUFFIX):
        try:
            payload = sig_bytes[: -len(ERC6492_MAGIC_SUFFIX)]
            # abi_decode ignores trailing data; payload is exactly (address, bytes, bytes)
            _factory, _factory_calldata, inner_sig = abi_decode(
                ['address', 'bytes', 'bytes'], payload,
            )
            log.info('eth_payer_signature: unwrapped ERC-6492 (inner sig %d bytes)', len(inner_sig))
            sig_bytes = inner_sig
        except Exception as e:
            log.warning('eth_payer_signature: failed to unwrap ERC-6492 payload: %s', e)
            return False

    # 2/3) ERC-1271 eth_call. We compute the EIP-191 hash the same way wallet
    # signers do for personal_sign; smart wallet contracts reconstruct the
    # same hash internally (for Coinbase Smart Wallet, via its WebAuthn
    # challenge matching).
    try:
        msg_bytes = message.encode('utf-8')
        prefix = f'\x19Ethereum Signed Message:\n{len(msg_bytes)}'.encode('utf-8')
        msg_hash = Web3.keccak(prefix + msg_bytes)
    except Exception as e:
        log.warning('eth_payer_signature: hash build failed: %s', e)
        return False

    payer_cs = Web3.to_checksum_address(payer)

    # Sanity: if the wallet has no code on this chain, ERC-1271 can't work.
    # Emit a useful error rather than a confusing eth_call revert.
    try:
        code = w3.eth.get_code(payer_cs)
    except Exception as e:
        log.warning('eth_payer_signature: get_code failed: %s', e)
        return False
    if not code or code == b'' or code == b'\x00':
        log.warning(
            'eth_payer_signature: payer %s has no contract code on this chain (counterfactual smart wallet not yet deployed)',
            payer,
        )
        return False

    # EIP-7702 detection: a delegated EOA's bytecode is `0xef0100 || <impl>`
    # (23 bytes total). MetaMask Smart Account in 7702 mode signs through the
    # delegated implementation, which often expects an ERC-7739-style nested
    # hash bound to the wallet's domain separator instead of the raw EIP-191
    # hash. Detect the prefix so we know to attempt the chain-bound retry.
    is_7702 = code[:3] == EIP7702_PREFIX

    # Try plain EIP-191 hash first. This is what CSW (and most smart accounts)
    # accept directly — they internally compute their own chain-bound hash and
    # verify the signature against it.
    magic = _try_erc1271(w3, payer_cs, msg_hash, sig_bytes)
    if magic == ERC1271_MAGIC:
        return True

    # Fallback for 7702-delegated EOAs (and any other smart account that wants
    # an ERC-7739 chain-bound envelope): retry with
    #   keccak256("\x19\x01" || DOMAIN_SEPARATOR() || msg_hash)
    # This works for any contract that exposes the standard EIP-712
    # `DOMAIN_SEPARATOR()` view (selector 0x3644e515) — covers OpenZeppelin
    # EIP712 base and most smart-account implementations including MetaMask
    # Smart Account on 7702.
    if is_7702:
        log.info(
            'eth_payer_signature: payer %s is EIP-7702-delegated (impl=0x%s); trying chain-bound retry',
            payer, code[3:23].hex() if len(code) >= 23 else '?',
        )
        domain_separator = _try_fetch_domain_separator(w3, payer_cs)
        if domain_separator is not None:
            chain_bound = Web3.keccak(b'\x19\x01' + domain_separator + msg_hash)
            magic_cb = _try_erc1271(w3, payer_cs, chain_bound, sig_bytes)
            if magic_cb == ERC1271_MAGIC:
                log.info(
                    'eth_payer_signature: 7702 chain-bound retry succeeded for %s',
                    payer,
                )
                return True
            log.warning(
                'eth_payer_signature: 7702 chain-bound retry returned %s (expected %s) for payer=%s',
                magic_cb.hex() if magic_cb else 'no-result',
                ERC1271_MAGIC.hex(), payer,
            )
        else:
            log.warning(
                'eth_payer_signature: 7702 wallet %s does not expose DOMAIN_SEPARATOR(); '
                'cannot perform chain-bound retry',
                payer,
            )

    log.warning(
        'eth_payer_signature: ERC-1271 returned non-magic bytes (got %s, expected %s) for payer=%s%s',
        magic.hex() if isinstance(magic, (bytes, bytearray)) else magic,
        ERC1271_MAGIC.hex(), payer,
        ' [7702-delegated]' if is_7702 else '',
    )
    return False
