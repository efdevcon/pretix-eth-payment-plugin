"""HTTP endpoints for the WalletConnect payment flow."""
import asyncio
import json
import logging
import os
import re
import secrets
import time
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.utils.timezone import now as tz_now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_scopes import scopes_disabled
from web3 import Web3

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address

from pretix.base.models import Event, Order
from pretix_eth.chains import (
    SUPPORTED_CHAINS, ALL_SYMBOLS, CHAIN_METADATA,
    is_supported,
)
from pretix_eth.models import WCPaymentAttempt
from pretix_eth.pricing import build_quote, fetch_eth_price_usd
from pretix_eth.payment import WalletConnectPayment
from pretix_eth.rpc import get_rpc_url
from pretix_eth.verification import verify_erc20_transfer, verify_native_eth
from pretix_eth.x402.auth import get_client_ip

log = logging.getLogger(__name__)

RATE_LIMIT_PER_MIN = int(os.environ.get('WC_VERIFY_RATE_LIMIT_PER_MIN', '10'))
# V52: primary per-IP-per-event cap. Attacker-controlled `quote_id` was
# rotating to bypass the per-quote bucket and burn merchant RPC quota; the
# IP-only cap forecloses that path. Default 20/min — a real buyer retrying
# through a flaky wallet session burns ~1-3 verifies (initial + manual hash
# fallback), so 20 leaves an order-of-magnitude headroom. Bumped down from
# 60/min after V52 verification showed the looser cap let a 12-quote
# rotation walk through unbounded.
WC_VERIFY_IP_RATE_LIMIT_PER_MIN = int(os.environ.get('WC_VERIFY_IP_RATE_LIMIT_PER_MIN', '20'))

# V53: pre-signature limits on /plugin/wc/create-quote/. The smart-wallet
# (ERC-1271) signature path verifies via an on-chain `isValidSignature`
# call, so bogus signatures drain merchant RPC quota. Two layers:
#   - WC_CREATE_QUOTE_IP_RATE_LIMIT_PER_MIN — per-IP+event budget, mirrors
#     the V52 limiter on /verify/. Default 20/min.
#   - WC_CREATE_QUOTE_PER_CHALLENGE_BUDGET — per-(order, challenge) failure
#     budget tracked in `payment.info_data['failed_sig_attempts']`. Once
#     exhausted the challenge must be re-issued. Catches the case where an
#     attacker rotates IPs against a single legitimate pending order.
WC_CREATE_QUOTE_IP_RATE_LIMIT_PER_MIN = int(os.environ.get('WC_CREATE_QUOTE_IP_RATE_LIMIT_PER_MIN', '20'))
WC_CREATE_QUOTE_PER_CHALLENGE_BUDGET = int(os.environ.get('WC_CREATE_QUOTE_PER_CHALLENGE_BUDGET', '5'))


def _check_rate_limit(quote_id: str, ip: str) -> bool:
    """Return False if caller has exceeded WC_VERIFY_RATE_LIMIT_PER_MIN for this quote+IP pair."""
    key = f'wc_verify_rl:{quote_id}:{ip}'
    count = cache.get(key, 0)
    if count >= RATE_LIMIT_PER_MIN:
        return False
    cache.set(key, count + 1, timeout=60)
    return True


def _check_wc_verify_ip_rate_limit(organizer: str, event: str, ip: str) -> bool:
    """V52: primary per-IP-per-event cap, checked BEFORE quote lookup or any
    RPC work. Attackers can rotate valid quote_ids to bypass `_check_rate_limit`
    (which keys on quote_id+ip), but the IP-keyed cap doesn't budge under
    that pattern and bounds RPC spend regardless of how many pending quotes
    the same IP has minted."""
    key = f'wc_verify_ip:{organizer}:{event}:{ip}'
    count = cache.get(key, 0)
    if count >= WC_VERIFY_IP_RATE_LIMIT_PER_MIN:
        return False
    cache.set(key, count + 1, timeout=60)
    return True


def _check_wc_create_quote_ip_rate_limit(organizer: str, event: str, ip: str) -> bool:
    """V53: per-IP+event rate limit on /plugin/wc/create-quote/, checked
    BEFORE any signature verification (ERC-1271 sig verify hits an on-chain
    `isValidSignature` call — bogus sigs would otherwise drain RPC quota).
    Same shape as the V52 limiter on /verify/, separate bucket so the two
    flows don't starve each other."""
    key = f'wc_create_quote_ip:{organizer}:{event}:{ip}'
    count = cache.get(key, 0)
    if count >= WC_CREATE_QUOTE_IP_RATE_LIMIT_PER_MIN:
        return False
    cache.set(key, count + 1, timeout=60)
    return True


def _check_buyer_order_access(request, event):
    """Validate `order_code` + `order_secret` (query-string for GET, body for
    POST) against an Order on this event. Returns the Order on success, or a
    JsonResponse with the appropriate 401/404 to short-circuit the view.

    Buyer-facing WC endpoints (`payment_options`, `wallet_balances`) used to
    have no auth at all — the wc_inject bundle running in the buyer's browser
    has no Pretix API token and the endpoints were public. That's strictly
    worse than the equivalent x402 endpoints, which require a TeamAPIToken
    (server-side only). The bundle DOES have the order's `code` and `secret`
    (Pretix's checkout template injects them as `WCConfig`), so we use those
    as the buyer credential — same protection level Pretix's own session-
    based AJAX endpoints use, with no new infrastructure.

    Symmetric 404 on missing order vs. wrong secret to prevent code-only
    enumeration; constant-time secret compare (`hmac.compare_digest`) to
    avoid the byte-by-byte timing leak of `==`."""
    from hmac import compare_digest
    order_code = (request.GET.get('order_code') or '').strip()
    order_secret = (request.GET.get('order_secret') or '').strip()
    if not (order_code and order_secret):
        body = _read_body(request)
        order_code = order_code or (body.get('order_code') or '').strip()
        order_secret = order_secret or (body.get('order_secret') or '').strip()
    if not (order_code and order_secret):
        return None, JsonResponse({'error': 'order_code and order_secret are required'}, status=401)
    with scopes_disabled():
        order = Order.objects.filter(code=order_code, event=event).first()
    if order is None or not compare_digest(order.secret, order_secret):
        return None, JsonResponse({'error': 'order not found or secret mismatch'}, status=404)
    return order, None


def _wc_buyer_rate_limit(client_ip: str, kind: str) -> bool:
    """Per-IP rate limit (300/min) for buyer-facing WC endpoints. `kind` keys
    a separate bucket per endpoint so a chatty payment-options call doesn't
    starve wallet-balances (and vice versa). Returns False when exhausted."""
    key = f'wc_buyer_rl:{kind}:{client_ip}'
    count = cache.get(key, 0)
    if count >= 300:
        return False
    cache.set(key, count + 1, timeout=60)
    return True


def _wc_config_or_403(event, *, chain_id=None, symbol=None):
    """V46: enforce the WC provider's enabled state + per-chain / per-token
    toggles on every raw `/plugin/wc/*` endpoint. Pre-fix code only consulted
    these settings in `payment_options` (the UI feed) — the create-quote /
    challenge / verify endpoints accepted any chain/token regardless. So an
    operator who flipped `payment_walletconnect__enabled=False` (or per-chain
    / per-token disable flags) still saw quotes mint and orders settle for
    those disabled rails.

    Returns `(provider, None)` on success, `(None, JsonResponse)` on
    rejection so callers can `if err: return err`."""
    provider = WalletConnectPayment(event)
    if not provider.settings.get('_enabled', as_type=bool, default=False):
        return None, JsonResponse({'error': 'walletconnect disabled'}, status=404)
    if chain_id is not None:
        v = str(provider.settings.get(f'chain_{chain_id}', default='True')).lower()
        if v not in ('true', '1', 'yes'):
            return None, JsonResponse({'error': 'chain disabled'}, status=400)
    if symbol is not None:
        v = str(provider.settings.get(f'token_{symbol}', default='True')).lower()
        if v not in ('true', '1', 'yes'):
            return None, JsonResponse({'error': 'token disabled'}, status=400)
    return provider, None


def _read_body(request) -> dict:
    try:
        return json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return {}


_TX_HASH_RE = re.compile(r'^0x[a-fA-F0-9]{64}$')


def _get_web3(chain_id: int, settings_key):
    url = get_rpc_url(chain_id, settings_key=settings_key)
    return Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))


@scopes_disabled()
def _get_provider_for_event(request: HttpRequest):
    """Resolve the event from query string (GET) or JSON body (POST),
    then instantiate our payment provider bound to that event."""
    from pretix.base.models import Event
    body = _read_body(request) if request.method == 'POST' else {}
    ev_slug = request.GET.get('event') or body.get('event')
    org_slug = request.GET.get('organizer') or body.get('organizer')
    if not ev_slug or not org_slug:
        return None
    try:
        event = Event.objects.get(slug=ev_slug, organizer__slug=org_slug)
    except Event.DoesNotExist:
        return None
    return WalletConnectPayment(event)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def payment_options(request, **kwargs):
    # Buyer auth + per-IP rate limit. Both endpoints used to be unauthenticated
    # and unrate-limited (strictly worse than V33). The wc_inject bundle has
    # `orderCode` + `orderSecret` injected into WCConfig by Pretix's checkout
    # template, so it can pass them as query params. Plugin validates and
    # gates per-IP at 30/min.
    client_ip = get_client_ip(request)
    if not _wc_buyer_rate_limit(client_ip, 'payment_options'):
        return JsonResponse({'error': 'rate limit exceeded'}, status=429)

    org_slug = (request.GET.get('organizer') or '').strip()
    ev_slug = (request.GET.get('event') or '').strip()
    if not (org_slug and ev_slug):
        return JsonResponse({'error': 'organizer and event are required'}, status=400)
    with scopes_disabled():
        try:
            event = Event.objects.get(slug=ev_slug, organizer__slug=org_slug)
        except Event.DoesNotExist:
            return JsonResponse({'error': 'event not found'}, status=404)

    _, err = _check_buyer_order_access(request, event)
    if err is not None:
        return err

    provider, err = _wc_config_or_403(event)
    if err is not None:
        return err

    # Read per-chain and per-token boolean settings (default: all enabled)
    enabled_chains = [
        cid for cid in SUPPORTED_CHAINS
        if str(provider.settings.get(f'chain_{cid}', default='True')).lower() in ('true', '1', 'yes')
    ]
    enabled_tokens = [
        sym for sym in ALL_SYMBOLS
        if str(provider.settings.get(f'token_{sym}', default='True')).lower() in ('true', '1', 'yes')
    ]
    receive_address = provider.settings.get('receive_address')

    options = []
    for cid in enabled_chains:
        for sym in enabled_tokens:
            if is_supported(cid, sym):
                options.append({
                    'chain_id': cid,
                    'chain_name': CHAIN_METADATA[cid]['name'],
                    'symbol': sym,
                })

    # ETH availability (dual-oracle). Capture the price too so the wc_inject
    # picker can do an accurate "is the wallet's ETH balance enough" check
    # without re-fetching the oracles client-side. Stays consistent with the
    # quote-creation endpoint, which uses the same `fetch_eth_price_usd()`.
    eth_available = True
    eth_disabled_reason = None
    eth_price_usd: Optional[float] = None
    if 'ETH' in enabled_tokens:
        try:
            result = asyncio.run(fetch_eth_price_usd())
            if result is None:
                eth_available = False
                eth_disabled_reason = 'oracle_unavailable_or_diverged'
            else:
                eth_price_usd = result.price
        except Exception as e:
            log.warning('ETH price fetch failed: %s', e)
            eth_available = False
            eth_disabled_reason = 'oracle_error'

    if not eth_available:
        options = [o for o in options if o['symbol'] != 'ETH']

    return JsonResponse({
        'options': options,
        'eth_available': eth_available,
        'eth_disabled_reason': eth_disabled_reason,
        'eth_price_usd': eth_price_usd,
        'receive_address': receive_address,
        'chain_metadata': {str(cid): CHAIN_METADATA[cid] for cid in enabled_chains},
    })


# ---------------------------------------------------------------------------
# Wallet balances (Zapper main + RPC fallback) — same engine as /plugin/x402
# ---------------------------------------------------------------------------


def _is_address(s: str) -> bool:
    return isinstance(s, str) and bool(re.match(r'^0x[a-fA-F0-9]{40}$', s))


@csrf_exempt
@require_http_methods(['GET'])
def wallet_balances(request, **kwargs):
    """Return per-(chain, token) balances for `wallet`, scoped to chains/tokens
    enabled in the event's plugin settings. Used by the wc_inject UI to gate
    the network/token picker on actual holdings, same as /plugin/x402's
    payment-options does for the devcon checkout.

    Reuses `fetch_balances_for_wallet` so the Zapper-first / RPC-fallback
    behaviour is identical across both flows. Failures (Zapper down, RPC
    flake) return an empty list — the UI should still render all options
    and just skip the balance badge."""
    from pretix_eth.x402.balances import fetch_balances_for_wallet

    client_ip = get_client_ip(request)
    if not _wc_buyer_rate_limit(client_ip, 'wallet_balances'):
        return JsonResponse({'error': 'rate limit exceeded'}, status=429)

    org_slug = (request.GET.get('organizer') or '').strip()
    ev_slug = (request.GET.get('event') or '').strip()
    if not (org_slug and ev_slug):
        return JsonResponse({'error': 'organizer and event are required'}, status=400)
    with scopes_disabled():
        try:
            event = Event.objects.get(slug=ev_slug, organizer__slug=org_slug)
        except Event.DoesNotExist:
            return JsonResponse({'error': 'event not found'}, status=404)

    _, err = _check_buyer_order_access(request, event)
    if err is not None:
        return err

    provider, err = _wc_config_or_403(event)
    if err is not None:
        return err

    wallet = (request.GET.get('wallet') or '').strip()
    if not _is_address(wallet):
        return JsonResponse({'error': 'wallet must be 0x + 40 hex'}, status=400)
    wallet = Web3.to_checksum_address(wallet)

    enabled_chains = [
        cid for cid in SUPPORTED_CHAINS
        if str(provider.settings.get(f'chain_{cid}', default='True')).lower() in ('true', '1', 'yes')
    ]
    if not enabled_chains:
        return JsonResponse({'wallet': wallet, 'balances': []})

    alchemy_key = provider.settings.get('alchemy_api_key', default=None) or None
    zapper_key = provider.settings.get('zapper_api_key', default=None) or None

    try:
        raw = fetch_balances_for_wallet(
            wallet=wallet, chain_ids=enabled_chains,
            alchemy_key=alchemy_key, zapper_api_key=zapper_key,
        )
    except Exception as e:
        # Best-effort: don't block the buyer if the balance lookup blows up.
        log.warning('wc_wallet_balances: fetch failed for %s: %s', wallet, e)
        raw = []

    return JsonResponse({'wallet': wallet, 'balances': raw})


CHALLENGE_TTL = 600  # 10 min


@csrf_exempt
@require_http_methods(['POST'])
def challenge(request, **kwargs):
    """Issue a signed-message challenge that the user's wallet must sign,
    proving ownership of the address that will pay."""
    from hmac import compare_digest
    body = _read_body(request)

    required = ('order_code', 'order_secret', 'organizer', 'event')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({'error': f'missing fields: {missing}'}, status=400)

    with scopes_disabled():
        try:
            event = Event.objects.get(slug=body['event'], organizer__slug=body['organizer'])
        except Event.DoesNotExist:
            return JsonResponse({'error': 'order not found or secret mismatch'}, status=404)

        # V46: bail if WC is disabled for this event before doing anything else.
        _, err = _wc_config_or_403(event)
        if err is not None:
            return err

        # V48: symmetric 404 for missing order vs. wrong secret + constant-time
        # secret compare. Pre-fix code returned 404 (missing) vs 403 (wrong secret),
        # which let any caller walk the order-code namespace.
        order = Order.objects.filter(code=body['order_code'], event=event).first()
        if order is None or not compare_digest(order.secret, body['order_secret']):
            return JsonResponse({'error': 'order not found or secret mismatch'}, status=404)

        if order.status != Order.STATUS_PENDING:
            return JsonResponse({'error': 'order not pending'}, status=409)

        nonce = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + CHALLENGE_TTL

        message = (
            'Pretix ticket payment\n'
            f'Order: {order.code}\n'
            f'Nonce: {nonce}\n'
            f'Expires: {expires_at}'
        )

        # Find or create the pending walletconnect payment and stash nonce on info_data
        payment = order.payments.filter(provider='walletconnect', state='created').first()
        if payment is None:
            payment = order.payments.create(
                provider='walletconnect',
                amount=order.total,
                state='created',
            )

        info = payment.info_data or {}
        info['challenge_nonce'] = nonce
        info['challenge_expires_at'] = expires_at
        info['challenge_message'] = message
        # V53: a fresh challenge clears the per-challenge failed-sig budget
        # so a buyer who burnt the budget can recover by re-issuing the
        # challenge. Attackers can also re-challenge, but each /challenge/
        # call needs a fresh order_code+order_secret (already V48-gated) and
        # the per-IP /create-quote/ rate limit caps the upstream volume.
        info.pop('failed_sig_attempts', None)
        payment.info_data = info
        payment.save()

    return JsonResponse({
        'nonce': nonce,
        'message': message,
        'expires_at': expires_at,
    })


@csrf_exempt
@require_http_methods(['POST'])
def create_quote(request, **kwargs):
    """Recover the payer from a SIWE-lite signature, validate the challenge,
    build a quote, and persist it to the pending payment's info_data."""
    from hmac import compare_digest
    body = _read_body(request)

    required = ('order_code', 'order_secret', 'organizer', 'event',
                'chain_id', 'symbol', 'nonce', 'signature')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({'error': f'missing fields: {missing}'}, status=400)

    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'error': 'invalid chain_id'}, status=400)

    symbol = body['symbol']
    if not is_supported(chain_id, symbol):
        return JsonResponse({'error': 'unsupported chain/token combination'}, status=400)

    # V53: pre-signature IP rate limit. The smart-wallet (ERC-1271) verify
    # path below makes an on-chain `isValidSignature` call per attempt — a
    # legitimate pending order/challenge is enough ammo to drain RPC quota
    # by submitting many bogus signatures. Cap fires before any sig work.
    client_ip = get_client_ip(request)
    if not _check_wc_create_quote_ip_rate_limit(body['organizer'], body['event'], client_ip):
        log.warning('wc_create_quote rejected: ip rate limit exceeded ip=%s', client_ip)
        return JsonResponse({'error': 'rate limit exceeded'}, status=429)

    with scopes_disabled():
        try:
            event = Event.objects.get(slug=body['event'], organizer__slug=body['organizer'])
        except Event.DoesNotExist:
            return JsonResponse({'error': 'order not found or secret mismatch'}, status=404)

        # V46: enforce WC enabled + per-chain + per-token toggles before
        # minting a quote. Pre-fix code only checked the global `is_supported`
        # registry, not the operator's per-event opt-out flags.
        _, err = _wc_config_or_403(event, chain_id=chain_id, symbol=symbol)
        if err is not None:
            return err

        # V48: symmetric 404 + constant-time secret compare (mirror of challenge).
        order = Order.objects.filter(code=body['order_code'], event=event).first()
        if order is None or not compare_digest(order.secret, body['order_secret']):
            return JsonResponse({'error': 'order not found or secret mismatch'}, status=404)

        payment = order.payments.filter(provider='walletconnect', state='created').first()
        if payment is None:
            return JsonResponse({'error': 'no pending walletconnect payment; call /challenge/ first'}, status=409)

        info = payment.info_data or {}
        stored_nonce = info.get('challenge_nonce')
        message = info.get('challenge_message')
        expires_at = info.get('challenge_expires_at', 0)

        if not stored_nonce or stored_nonce != body['nonce']:
            return JsonResponse({'error': 'nonce mismatch'}, status=400)
        if time.time() > expires_at:
            return JsonResponse({'error': 'challenge expired'}, status=400)

        # V53: per-challenge failed-sig budget. Catches the case where an
        # attacker rotates IPs (defeating the per-IP limiter above) against
        # a single legitimate pending order/challenge. Once the budget is
        # spent the buyer must request a fresh /challenge/ — which resets
        # `failed_sig_attempts` to 0 implicitly via the new challenge's
        # info_data overwrite.
        failed_sigs = int(info.get('failed_sig_attempts', 0))
        if failed_sigs >= WC_CREATE_QUOTE_PER_CHALLENGE_BUDGET:
            log.warning(
                'wc_create_quote rejected: per-challenge budget exhausted (%d/%d) order=%s',
                failed_sigs, WC_CREATE_QUOTE_PER_CHALLENGE_BUDGET, order.code,
            )
            return JsonResponse({
                'error': 'too many failed signature attempts for this challenge; request a new challenge',
            }, status=429)

        # Two acceptable signature modes:
        #
        # 1) EOA (65 bytes): standard ECDSA. We recover the signer locally and
        #    use it as the payer. No on-chain lookup needed.
        #
        # 2) Smart wallet (ERC-1271 / ERC-6492, variable length — Coinbase/Base
        #    Smart Wallet returns ~640 bytes): the signature is a contract-level
        #    proof, NOT an ECDSA signature, so `Account.recover_message` throws
        #    with "Unexpected recoverable signature length". The client MUST
        #    provide `payer_address` alongside the signature so we can verify
        #    it via ERC-1271's isValidSignature eth_call (same code path as the
        #    x402 flow's eth_payer_signature).
        claimed_payer = body.get('payer_address')
        signature_hex = body['signature']
        sig_len_bytes = len(signature_hex[2:]) // 2 if signature_hex.startswith('0x') else len(signature_hex) // 2

        def _record_sig_failure():
            """V53: bump `failed_sig_attempts` on the pending payment so the
            per-challenge budget catches IP-rotating brute-force. Save is
            best-effort — failing to record the failure shouldn't itself
            500 the response."""
            try:
                info['failed_sig_attempts'] = failed_sigs + 1
                payment.info_data = info
                payment.save(update_fields=['info'])
            except Exception as e:
                log.warning('wc_create_quote: failed to record sig failure: %s', e)

        if sig_len_bytes == 65 and not claimed_payer:
            # EOA path (backward-compatible with clients that don't send payer_address)
            try:
                msg = encode_defunct(text=message)
                recovered = Account.recover_message(msg, signature=signature_hex)
            except Exception as e:
                _record_sig_failure()
                return JsonResponse({'error': f'signature recovery failed: {e}'}, status=400)
            payer = to_checksum_address(recovered)
        else:
            if not claimed_payer:
                # Shape error, not a sig failure — don't burn the budget.
                return JsonResponse({
                    'error': (
                        'payer_address is required for smart-wallet signatures '
                        f'(got {sig_len_bytes}-byte signature, not a 65-byte ECDSA)'
                    ),
                }, status=400)
            provider = WalletConnectPayment(order.event)
            settings_key = provider.settings.get('alchemy_api_key', default=None)
            from pretix_eth.verification import verify_eth_payer_signature
            # Coinbase/Base Smart Wallet (and other ERC-1271 wallets that use
            # EIP-712 domain separators) bind signatures to the chain the
            # wallet was on at signing time — the `replaySafeHash` wrapper
            # pulls chainId from `block.chainid`, so a signature made on
            # chain X validates ONLY when isValidSignature is called on
            # chain X.
            #
            # V11 hardening: we used to enumerate the full SUPPORTED_CHAINS
            # list as a "try each chain until something validates" fallback.
            # That's an attack-surface multiplier — every extra chain is
            # another chance for an unrelated contract at the same address
            # on a different chain to coincidentally validate the signature.
            # We now only try the two chains the buyer explicitly said
            # matter:
            #   1. `signing_chain_id` (wallet's chain at sign time, if sent)
            #   2. the settlement chain (`chain_id`)
            # If the smart wallet legitimately signed on neither, the buyer
            # has to switch to the settlement chain and re-sign — same
            # ergonomic cost as for any other multi-chain wallet, with the
            # broad cross-chain replay vector closed.
            signing_chain_id = body.get('signing_chain_id')
            check_chain_ids: list = []
            if signing_chain_id is not None:
                try:
                    check_chain_ids.append(int(signing_chain_id))
                except (TypeError, ValueError):
                    pass
            if chain_id not in check_chain_ids:
                check_chain_ids.append(chain_id)
            # Coinbase / Base Smart Wallet always wraps ERC-1271 sigs with
            # its "home" chain (mainnet) regardless of what wagmi reports
            # as the wallet's current chain — the SDK has a chain-id desync
            # bug (coinbase-wallet-sdk#1317) where the connector lies about
            # getChainId(). Empirically: a CBSW user with wagmi-state on
            # Arbitrum signs with chainId=1, and the only chain whose
            # contract validates the resulting sig is mainnet.
            #
            # Adding mainnet as a third check candidate fixes that without
            # opening a replay vector — the message body still embeds
            # order_code + single-use nonce + payer_address, so a sig
            # validated on mainnet still only binds the specific buyer
            # to the specific order. The V11 hardening was about closing
            # *unrelated-contract* coincidence on arbitrary chains; chain
            # 1 isn't arbitrary for smart wallets, every one has a mainnet
            # deployment.
            if 1 not in check_chain_ids:
                check_chain_ids.append(1)
            sig_ok = False
            for cid in check_chain_ids:
                try:
                    w3_for_sig = _get_web3(cid, settings_key)
                    if verify_eth_payer_signature(
                        w3=w3_for_sig, payer=claimed_payer, message=message, signature=signature_hex,
                    ):
                        sig_ok = True
                        break
                except Exception as e:
                    log.warning('eth_payer_signature chain %s verify errored: %s', cid, e)
            if not sig_ok:
                _record_sig_failure()
                return JsonResponse({
                    'error': (
                        'signature does not validate against payer_address '
                        '(checked chain(s): ' + ','.join(str(c) for c in check_chain_ids) + ')'
                    ),
                }, status=400)
            payer = to_checksum_address(claimed_payer)

        # ETH price (only if symbol == 'ETH')
        eth_price = None
        if symbol == 'ETH':
            result = asyncio.run(fetch_eth_price_usd())
            if result is None:
                return JsonResponse({'error': 'ETH temporarily unavailable'}, status=503)
            eth_price = result.price

        provider = WalletConnectPayment(order.event)
        receive_address = provider.settings.get('receive_address')
        if not receive_address:
            return JsonResponse({'error': 'receive_address not configured'}, status=500)
        ttl = int(provider.settings.get('quote_ttl_seconds', default=600))

        quote = build_quote(
            order_code=order.code,
            order_total_usd=Decimal(str(order.total)),
            chain_id=chain_id, symbol=symbol, payer=payer,
            receive_address=receive_address,
            eth_price=eth_price, ttl_seconds=ttl,
        )

        info['quote'] = quote
        # V53: clear the failed-sig counter on success so a buyer who hit
        # one bad sig and corrected it doesn't carry the budget tax into
        # future quote builds on the same challenge.
        info.pop('failed_sig_attempts', None)
        payment.info_data = info
        payment.save()

    return JsonResponse(quote)


def _verify_bad(reason: str, status: int = 400, **extra):
    """Return a 4xx JsonResponse AND log the reason so production 'Bad Request:
    /plugin/wc/verify/' lines in the Django middleware log become diagnosable
    without having to reproduce. The response body shape is unchanged so the
    frontend retry logic keeps working."""
    log.warning('wc_verify rejected: %s (extra=%s)', reason, extra or '-')
    return JsonResponse({'error': reason}, status=status)


@csrf_exempt
@require_http_methods(['POST'])
def verify(request, **kwargs):
    """Full verification chain:
    1. Input validation
    2. One-time tx_hash check
    3. Look up order + quote
    4. Chain/quote expiry checks
    5. On-chain verify (web3.py)
    6. Atomic claim + Pretix payment.confirm()
    """
    body = _read_body(request)

    required = ('quote_id', 'tx_hash', 'chain_id', 'organizer', 'event')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return _verify_bad(f'missing fields: {missing}')

    client_ip = get_client_ip(request)
    # V52: primary per-IP-per-event cap fires before any quote lookup. The
    # secondary per-quote cap below catches one buyer hammering a single
    # quote — but the per-IP one is what bounds the cost of attackers who
    # rotate fresh quote_ids to escape the per-quote bucket.
    if not _check_wc_verify_ip_rate_limit(body['organizer'], body['event'], client_ip):
        return _verify_bad('rate limit exceeded (ip)', status=429, ip=client_ip)
    if not _check_rate_limit(body['quote_id'], client_ip):
        return _verify_bad('rate limit exceeded', status=429, quote_id=body.get('quote_id'), ip=client_ip)

    tx_hash = body['tx_hash']
    if not _TX_HASH_RE.match(tx_hash):
        return _verify_bad('invalid tx_hash format', tx_hash=tx_hash)
    # V45: canonicalise hex case before any check or insert. WCPaymentAttempt's
    # unique constraint is case-sensitive at the DB level; pre-fix code did an
    # `__iexact` pre-check then inserted with caller casing, so two concurrent
    # verifies for the same on-chain tx with different casing both passed
    # the pre-check, both inserted, both orders went paid.
    tx_hash = tx_hash.lower()

    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return _verify_bad('invalid chain_id', chain_id=body.get('chain_id'))

    # Fail fast on one-time tx_hash check. Now exact-match against the
    # canonicalised lowercase form (see V45 note above).
    if WCPaymentAttempt.objects.filter(tx_hash=tx_hash, state='completed').exists():
        return _verify_bad('tx already used for a completed order', tx_hash=tx_hash)

    with scopes_disabled():
        # Find the order by matching quote_id in any pending walletconnect payment
        try:
            order = Order.objects.get(
                event__slug=body['event'],
                event__organizer__slug=body['organizer'],
                payments__provider='walletconnect',
                payments__state='created',
            )
        except Order.DoesNotExist:
            return _verify_bad('order not found', status=404,
                               event=body.get('event'), organizer=body.get('organizer'))
        except Order.MultipleObjectsReturned:
            # Multiple pending orders on event — disambiguate by quote_id below
            order = None

        # Find the payment with matching quote_id
        if order is None:
            candidates = Order.objects.filter(
                event__slug=body['event'],
                event__organizer__slug=body['organizer'],
                payments__provider='walletconnect',
                payments__state='created',
            ).distinct()
        else:
            candidates = [order]

        payment = None
        for candidate in candidates:
            for p in candidate.payments.filter(provider='walletconnect', state='created'):
                if (p.info_data or {}).get('quote', {}).get('quote_id') == body['quote_id']:
                    order = candidate
                    payment = p
                    break
            if payment is not None:
                break

        if payment is None:
            return _verify_bad('quote not found', status=404, quote_id=body.get('quote_id'))

        quote = payment.info_data['quote']

        if chain_id != quote['chain_id']:
            return _verify_bad('chain_id mismatch',
                               submitted=chain_id, quote=quote.get('chain_id'))

        if time.time() > quote['expires_at']:
            return _verify_bad('quote expired',
                               expires_at=quote['expires_at'], now=int(time.time()))

        # V46: re-check the WC config at settlement time. An operator can flip
        # the provider/chain/token toggles off between quote creation and
        # verify; without this re-check, in-flight quotes would still settle
        # against now-disabled rails.
        _, err = _wc_config_or_403(order.event, chain_id=chain_id, symbol=quote.get('symbol'))
        if err is not None:
            return err

        provider = WalletConnectPayment(order.event)
        settings_key = provider.settings.get('alchemy_api_key', default=None)
        min_conf = int(provider.settings.get('min_confirmations', default=1))

        w3 = _get_web3(chain_id, settings_key)

        amount_raw = int(quote['amount_raw'])
        if quote['symbol'] == 'ETH':
            vr = verify_native_eth(
                w3=w3, tx_hash=tx_hash,
                expected_from=quote['intended_payer'],
                expected_to=quote['receive_address'],
                expected_amount_wei=amount_raw,
                min_confirmations=min_conf,
            )
        else:
            vr = verify_erc20_transfer(
                w3=w3, chain_id=chain_id, tx_hash=tx_hash,
                expected_from=quote['intended_payer'],
                expected_to=quote['receive_address'],
                expected_token=quote['token_address'],
                expected_amount=amount_raw,
                min_confirmations=min_conf,
            )

        if not vr.verified:
            log.warning('wc_verify rejected: on-chain verify failed: %s (tx=%s)', vr.error, tx_hash)
            # Surface confirmation progress for the wc_inject UI's progress bar.
            return JsonResponse({
                'verified': False,
                'error': vr.error,
                'confirmations': vr.confirmations,
                'confirmations_required': vr.min_confirmations,
            }, status=400)

        # V49: bind the on-chain transfer to the quote's freshness window.
        # Without this, any prior matching transfer (e.g. a refund, a stale
        # canceled-quote transfer, or an out-of-band send to the merchant)
        # could be replayed once into a future quote. The plain ERC-20
        # `Transfer` log carries no order/quote binding, so the only way to
        # require "this transfer was made FOR this quote" is to constrain the
        # block timestamp to the quote window.
        try:
            receipt_block = w3.eth.get_block(vr.block_number)
            block_ts = int(receipt_block.timestamp)
        except Exception as e:
            return _verify_bad(f'failed to fetch block timestamp: {e}', tx_hash=tx_hash)
        quote_created = int(quote.get('created_at', 0))
        quote_expires = int(quote.get('expires_at', 0))
        if quote_created and block_ts < quote_created:
            return _verify_bad('tx mined before quote was issued',
                               block_ts=block_ts, quote_created=quote_created, tx_hash=tx_hash)
        if quote_expires and block_ts > quote_expires:
            return _verify_bad('tx mined after quote expired',
                               block_ts=block_ts, quote_expires=quote_expires, tx_hash=tx_hash)

        # Atomic claim: unique constraint on tx_hash prevents race; the
        # SELECT FOR UPDATE on Order + re-check of order.status closes the
        # V51 window (mark_order_expired() flipped the order to expired
        # while a verify was mid-flight). The dup pre-check above is racey
        # by itself; the unique-constraint catch in `except IntegrityError`
        # below is the actual one-time-use guarantee.
        try:
            with transaction.atomic():
                # V51: re-fetch the order under a row lock and re-check it
                # is still pending + still within its payment deadline.
                order = Order.objects.select_for_update().get(pk=order.pk)
                if order.status != Order.STATUS_PENDING:
                    return _verify_bad('order is not in pending state',
                                       status=410, order_status=order.status, tx_hash=tx_hash)
                if order.expires and order.expires < tz_now():
                    return _verify_bad('order payment deadline has elapsed',
                                       status=410, order_expires=str(order.expires), tx_hash=tx_hash)

                WCPaymentAttempt.objects.create(
                    tx_hash=tx_hash, quote_id=quote['quote_id'],
                    order_code=order.code, payer=quote['intended_payer'],
                    chain_id=chain_id, state='completed',
                )

                info = payment.info_data or {}
                info['tx_hash'] = tx_hash
                info['chain_id'] = chain_id
                info['token_symbol'] = quote['symbol']
                info['token_address'] = quote.get('token_address')
                info['payer'] = quote['intended_payer']
                # Store as a plain integer string — the payment_control_render
                # helper formats it to human-readable decimals using the token
                # symbol. The old `f"{raw} (raw)"` format leaked into the Pretix
                # admin UI as literal text.
                info['amount'] = str(quote['amount_raw'])
                info['block_number'] = vr.block_number
                payment.info_data = info
                payment.save()

                # Render the payment recap for the order-paid email. The paid
                # email path uses `{payment_info}` = whatever we pass as
                # `mail_text=` to payment.confirm() — it does NOT call
                # `order_pending_mail_render` on its own. Without this, the
                # confirmation email's {payment_info} placeholder renders empty.
                try:
                    mail_text = WalletConnectPayment(order.event).order_pending_mail_render(order, payment)
                except Exception as e:
                    log.warning('[wc verify] failed to render mail_text for %s: %s', order.code, e)
                    mail_text = ''
                payment.confirm(mail_text=mail_text)
        except IntegrityError:
            return _verify_bad('tx already used (race)', status=409, tx_hash=tx_hash)

    return JsonResponse({
        'verified': True,
        'block_number': vr.block_number,
        'order_code': order.code,
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def client_info(request, **kwargs):
    """Fire-and-forget telemetry beacon from the wc_inject bundle.

    The bundle calls this once per wallet connection (via
    navigator.sendBeacon) so we can see, from the server logs, which
    wallets and connection types buyers actually use. There's no
    server-side state change: we emit a single structured log line and
    return 204.

    Two phases are emitted, each greppable on its own:
      - phase=connect : fired once when a wallet connects
      - phase=pay     : fired when the buyer initiates the payment
    so you can compare "who connected" vs "who actually tried to pay":
      grep '\\[wc-client\\] phase=connect' app.log | grep -o 'wallet=[^ ]*' | sort | uniq -c
      grep '\\[wc-client\\] phase=pay'     app.log | grep -o 'wallet=[^ ]*' | sort | uniq -c

    Values are buyer-supplied (client-side wallet name / connection
    kind), so they're truncated and treated as untrusted display strings
    only; nothing here is used for authz or persisted. The endpoint is
    per-IP rate limited like the other buyer endpoints to stop a client
    spamming the log."""
    client_ip = get_client_ip(request)
    if not _wc_buyer_rate_limit(client_ip, 'client_info'):
        # Quietly accept-and-drop: a beacon isn't worth a visible error,
        # and the caller (sendBeacon) ignores the response anyway.
        return HttpResponse(status=204)

    def _clip(k, n=64):
        # Read from query string first then POST body. navigator.sendBeacon
        # issues a POST but the bundle puts the fields in the URL query,
        # so GET-first covers both the beacon and a manual GET/POST.
        v = request.GET.get(k) or request.POST.get(k) or ''
        return v.strip().replace('\n', ' ').replace('\r', ' ')[:n]

    # `phase` leads the line (right after the tag) so each event type is a
    # fixed-prefix grep: `grep '[wc-client] phase=pay'`.
    #
    # Fields chosen for debugging the failure modes we actually see:
    #   wallet_chain vs picked_chain  → reveals a needed chain switch
    #     (the classic "internal error" cause when a mobile wallet is on
    #     the wrong network)
    #   is_safe                       → smart-account / Safe path, which
    #     has a different signing + confirmation flow
    #   ver                           → plugin version, to correlate a
    #     spike of failures with a deploy
    #   ua                            → browser/OS for platform-specific
    #     wallet quirks (iOS Safari popup blocking, in-wallet browsers)
    phase = _clip('phase', 16) or 'unknown'
    log.info(
        '[wc-client] phase=%s order=%s wallet=%s conn=%s wallet_chain=%s '
        'picked_chain=%s picked_token=%s is_safe=%s ver=%s addr=%s ua=%s',
        phase,
        _clip('order_code', 16),
        _clip('wallet_name'),
        _clip('connection_kind', 24),
        _clip('wallet_chain', 12),
        _clip('picked_chain', 12),
        _clip('picked_token', 16),
        _clip('is_safe', 5),
        _clip('plugin_version', 24),
        _clip('address', 42),
        _clip('ua', 180),
    )
    return HttpResponse(status=204)
