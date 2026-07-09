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
    # Surfaced even when `verified=False` so the buyer-facing UI can render
    # a confirmation progress bar (X/N) instead of an opaque spinner.
    confirmations: Optional[int] = None
    min_confirmations: Optional[int] = None


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
    confirmations = max(0, head - block)
    if confirmations < min_confirmations:
        return VerificationResult(
            False, error=f'insufficient confirmations ({confirmations}/{min_confirmations})',
            confirmations=confirmations, min_confirmations=min_confirmations,
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
        # V49: reject overpay too. ERC-20 quotes are signed against an exact
        # amount (USDC/USDT have no slippage); a transfer that moved more
        # tokens than the quote requires is some other transfer accidentally
        # matched, not the buyer's authorization for this order.
        if value > expected_amount:
            return VerificationResult(False, error=f'amount mismatch: {value} != {expected_amount}')
        return VerificationResult(True, block_number=block)

    return VerificationResult(False, error='no matching transfer found in tx')


def _prestate_diff(w3, tx_hash: str):
    """Fetch prestateTracer diffMode for the EXACT tx hash. Returns the diff
    dict {'pre': {...}, 'post': {...}} or None if the RPC gave no usable diff
    (unsupported debug_*, transient error). Requires Alchemy/enterprise RPC.

    This replaces the old callTracer frame-walk: matching a single {from,to,value}
    frame settles a native-ETH order PAID while the recipient nets 0 ETH. Six
    classes defeat frame-walking (reverted inner CALL, value-bearing DELEGATECALL,
    ancestor-revert, pay-then-forward, doctored trace, SELFDESTRUCT-in-reverted
    subtree). The only question that survives all of them is "did the recipient's
    balance actually go up and stay up, and did the payer actually pay" — which is
    exactly a net-balance delta, not a per-frame inspection."""
    try:
        resp = w3.provider.make_request(
            'debug_traceTransaction',
            [tx_hash, {'tracer': 'prestateTracer', 'tracerConfig': {'diffMode': True}}],
        )
    except Exception as e:
        log.warning('prestateTracer diffMode request failed for %s: %s', tx_hash, e)
        return None
    if not isinstance(resp, dict) or resp.get('error'):
        log.warning('prestateTracer diffMode error for %s: %s', tx_hash,
                    resp.get('error') if isinstance(resp, dict) else resp)
        return None
    result = resp.get('result')
    if not isinstance(result, dict):
        return None
    return result


def _net_balance_delta(diff: dict, addr: str) -> int:
    """post[addr].balance - pre[addr].balance under diffMode. diffMode lists
    only accounts whose net state changed; an account absent from both pre and
    post had an unchanged (zero) net balance. An account present only in `pre`
    (state read but net-unchanged) defaults post to its pre balance (delta 0);
    an account present only in `post` had a pre balance of 0."""
    def _hexbal(v):
        if v is None:
            return 0
        return int(v, 16) if isinstance(v, str) else int(v)
    addr = _normalize_hex(addr).lower()
    pre = {_normalize_hex(k).lower(): v for k, v in (diff.get('pre') or {}).items()}
    post = {_normalize_hex(k).lower(): v for k, v in (diff.get('post') or {}).items()}
    in_pre, in_post = addr in pre, addr in post
    if not in_pre and not in_post:
        return 0
    pre_b = _hexbal(pre.get(addr, {}).get('balance')) if in_pre else 0
    post_b = _hexbal(post.get(addr, {}).get('balance')) if in_post else pre_b
    return post_b - pre_b


def _verify_eth_net_delta(w3, tx_hash: str, from_lower: str, to_lower: str,
                          min_value: int) -> str:
    """Value-question oracle replacing the callTracer frame walk. Asks 'did the
    recipient actually gain >= min_value ETH net, and did the payer actually pay
    for it, in THIS tx?' — the only question that survives every phantom class:
      - reverted subtree contributes no net diff (kills v62/v66/v67/v80)
      - an in-tx forward-out nets recipient to 0 (kills v74)
      - same-node prestate reconciliation detects a doctored callTracer (kills v78)
    Returns 'match' | 'no_match' | 'trace_unavailable'. Requires a trace-capable
    (Alchemy/enterprise) RPC; public fallbacks without debug_* classify as
    'trace_unavailable' rather than false-rejecting."""
    diff = _prestate_diff(w3, tx_hash)
    if diff is None:
        return 'trace_unavailable'
    recipient_delta = _net_balance_delta(diff, to_lower)
    payer_delta = _net_balance_delta(diff, from_lower)
    # Recipient must NET a gain of at least min_value; payer must NET a debit of
    # at least min_value. When payer == tx.from, gas makes the debit strictly
    # larger, so `<= -min_value` is safe either way. Requiring both closes
    # pay-then-forward (recipient credited then debited nets 0) and reverted /
    # delegatecall / phantom classes (recipient never nets the gain).
    if recipient_delta >= min_value and payer_delta <= -min_value:
        return 'match'
    log.info('eth net-delta reject %s: recipient_delta=%s payer_delta=%s min=%s',
             tx_hash, recipient_delta, payer_delta, min_value)
    return 'no_match'


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
    confirmations = max(0, head - block)
    if confirmations < min_confirmations:
        return VerificationResult(
            False, error=f'insufficient confirmations ({confirmations}/{min_confirmations})',
            confirmations=confirmations, min_confirmations=min_confirmations,
        )

    min_wei = _min_acceptable_wei(expected_amount_wei)
    from_lower = _normalize_hex(expected_from).lower()
    to_lower = _normalize_hex(expected_to).lower()

    # Authoritative check for EVERY native-ETH settlement, EOA direct sends
    # included. The old tx.value happy path is unsafe: v74's pay-then-forward
    # settles a genuinely-successful, nothing-reverts tx where the recipient is
    # credited then debited in the same tx (net 0). Only a net-balance delta on
    # the recipient (plus a matching payer debit), keyed to this exact tx hash and
    # cross-checked against receipt.status (already enforced above), answers the
    # single question that survives every phantom class: did the money actually
    # reach the recipient and stay there, and did the payer pay for it?
    outcome = _verify_eth_net_delta(w3, tx_hash, from_lower, to_lower, min_wei)
    if outcome == 'match':
        return VerificationResult(True, block_number=block)
    if outcome == 'trace_unavailable':
        # RPC didn't give us a usable prestate diff — could be transient indexer
        # lag or the RPC provider doesn't support debug_*. Returning an "rpc
        # error" message makes the frontend auto-retry. A trace-capable
        # (Alchemy/enterprise) RPC is required for native-ETH settlement.
        return VerificationResult(
            False,
            error=f'RPC error: prestateTracer diffMode unavailable for {tx_hash}',
        )

    return VerificationResult(
        False,
        error=f'no net ETH transfer: recipient {expected_to} did not net ≥{min_wei} wei '
              f'from {expected_from} in {tx_hash} '
              f'(reverted / forwarded-out / delegatecall / phantom); '
              f'quote was {expected_amount_wei}, slippage tolerance {SLIPPAGE_BPS / 100:.2f}%',
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


# V86: bound the per-call cost of the ERC-1271 isValidSignature eth_call. A
# hostile 1271 validator can burn the node's block-gas-limit of compute per
# create-quote (IP-independent DoS) if the call runs uncapped. 200k gas is ample
# for real ERC-1271 / Safe / Coinbase-Smart-Wallet validators.
ISVALIDSIG_GAS_CAP = 200_000


def _try_erc1271(w3, payer_cs: str, hash_to_check: bytes, sig_bytes: bytes) -> Optional[bytes]:
    """Call isValidSignature(bytes32, bytes) on `payer_cs`. Returns the magic
    bytes (or whatever the contract returned) on success, or None if the call
    reverted / returned garbage."""
    from eth_abi import encode as abi_encode
    selector = bytes.fromhex('1626ba7e')
    try:
        encoded_args = abi_encode(['bytes32', 'bytes'], [hash_to_check, sig_bytes])
        calldata = '0x' + (selector + encoded_args).hex()
        result = w3.eth.call({'to': payer_cs, 'data': calldata, 'gas': ISVALIDSIG_GAS_CAP})
    except Exception as e:
        log.warning(
            'eth_payer_signature: isValidSignature eth_call reverted on %s: %s',
            payer_cs, e,
        )
        return None
    # ERC-1271 magic is 32 bytes; anything longer is a garbage/grief return.
    if isinstance(result, (bytes, bytearray)):
        if len(result) > 64:
            return None
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
    # If recovery succeeded but to a *different* address, REJECT outright —
    # don't fall through to ERC-1271. Falling through was the V19 attack
    # vector: an attacker submits `payer=victim-smart-wallet-addr` plus a
    # signature that recovers to their own EOA, and a permissive 1271
    # validator returns MAGIC for it, granting access. By rejecting here we
    # close that path; legitimate smart-wallet signatures that aren't
    # 65-byte ECDSA blobs (Safe multisig, CSW WebAuthn, etc.) recover to
    # nothing or throw, so they reach the ERC-1271 path below as before.
    if recovered and not _addr_eq(recovered, payer):
        log.warning(
            'eth_payer_signature: ECDSA recovered %s but expected payer=%s '
            '— rejecting (V19 hardening)',
            recovered, payer,
        )
        return False

    # Normalize sig bytes
    try:
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith('0x') else signature)
    except Exception as e:
        log.warning('eth_payer_signature: invalid hex signature: %s', e)
        return False

    # V77 hardening: refuse the Safe approved-hash static part
    # {r=owner, s=0, v in (0,1)}. It carries NO ECDSA material — the owner
    # pre-approves the digest on-chain via approveHash() and then submits a
    # purely static 65-byte blob. `s == 0` makes ECDSA recovery raise (so the
    # V19 recovered!=payer reject above never fires), and the v58 zero-sig probe
    # only tests v==0, so this shape would otherwise reach the ERC-1271 branch
    # and validate with no signature ever produced. `v==0/s==0` is the probe
    # shape and `v==1/s==0` is the Safe approveHash shape; neither is a real
    # signature. Legitimate ECDSA uses v in (27,28) — or (0,1) only with a
    # non-zero s — and real multi-owner Safe bundles are >65 bytes, so this
    # rejects only the no-material shapes.
    if len(sig_bytes) == 65:
        v = sig_bytes[64]
        s = int.from_bytes(sig_bytes[32:64], 'big')
        if s == 0 and v in (0, 1):
            log.warning(
                'eth_payer_signature: refusing v=%d/s=0 static part for payer=%s '
                '(no ECDSA material; V77 hardening)', v, payer,
            )
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

    # V19 hardening: refuse permissive ERC-1271 contracts that return MAGIC
    # for an all-zero signature. A handful of (mis)deployed "validators" do
    # this — they're effectively always-true and would treat any caller as
    # authorized. Probe with a 65-byte zero signature (most common shape;
    # legitimate validators all reject it) and bail before trusting this
    # contract's word on anything.
    zero_sig_probe = _try_erc1271(w3, payer_cs, msg_hash, b'\x00' * 65)
    if zero_sig_probe == ERC1271_MAGIC:
        log.warning(
            'eth_payer_signature: payer %s validates zero-sig — refusing '
            'permissive ERC-1271 contract (V19 hardening)',
            payer,
        )
        return False

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
