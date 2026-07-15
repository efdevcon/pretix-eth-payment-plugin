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


def _rate_limited(error='rate limit exceeded', *, retry_after=10, **extra):
    """429 JsonResponse with a `Retry-After` header (seconds) so the client
    backs off for a precise window instead of guessing. Buyer-facing rate
    limits use a short window (the cache buckets reset in <=60s and verify
    polling wants to resume promptly), so 10s is a sane default; callers can
    override per-endpoint. `extra` is merged into the JSON body to preserve
    existing fields (e.g. ip / quote_id) some callers include."""
    resp = JsonResponse({'error': error, **extra}, status=429)
    resp['Retry-After'] = str(int(retry_after))
    return resp


RATE_LIMIT_PER_MIN = int(os.environ.get('WC_VERIFY_RATE_LIMIT_PER_MIN', '10'))
# Primary per-IP-per-event cap. Attacker-controlled `quote_id` was rotating
# to bypass the per-quote bucket and burn merchant RPC quota; the IP-only
# cap forecloses that path.
#
# Default 120/min. The original 20 assumed ~1-3 verifies per buyer, but the
# bundle polls verify across the whole confirmation window: at the new 6 s
# mainnet cadence one buyer does ~6-7 polls, so 20 was tripped by just 2-3
# concurrent buyers behind one NAT (a shared office IP). 120 covers ~17
# concurrent mainnet buyers per IP while still bounding quote-rotation abuse
# — and the real abuse chokepoints remain the per-quote cap (10/min) and
# the signature-gated create-quote cap (20/min/IP), which an attacker must
# pass to mint each fresh quote_id in the first place.
WC_VERIFY_IP_RATE_LIMIT_PER_MIN = int(os.environ.get('WC_VERIFY_IP_RATE_LIMIT_PER_MIN', '120'))

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


# Per-IP-per-endpoint cap for the cheap, chatty buyer endpoints
# (payment-options, wallet-balances, client-info). 300 was set when the IP
# always resolved to the shared 'unknown' bucket (so it had to absorb the
# whole event); now that get_client_ip yields real per-IP buckets and P2
# polling discipline cut the call volume, a normal buyer uses only a handful
# per minute. 120/min keeps generous headroom for a large NAT'd office
# (~40 concurrent buyers at ~3 calls/min each) while not letting one IP
# drive 300 Zapper-backed balance lookups a minute.
WC_BUYER_RATE_LIMIT_PER_MIN = int(os.environ.get('WC_BUYER_RATE_LIMIT_PER_MIN', '120'))


def _wc_buyer_rate_limit(client_ip: str, kind: str) -> bool:
    """Per-IP rate limit for buyer-facing WC endpoints. `kind` keys a
    separate bucket per endpoint so a chatty payment-options call doesn't
    starve wallet-balances (and vice versa). Returns False when exhausted."""
    key = f'wc_buyer_rl:{kind}:{client_ip}'
    count = cache.get(key, 0)
    if count >= WC_BUYER_RATE_LIMIT_PER_MIN:
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
        return _rate_limited()

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
        return _rate_limited()

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
        return _rate_limited()

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

        # Signer-binding fields captured for settlement-time re-validation
        # (V75/V79 TOCTOU): the exact chain that validated, and (for smart
        # wallets) the payer's on-chain code prefix at quote time.
        validated_chain = None
        payer_code_prefix = None
        if sig_len_bytes == 65 and not claimed_payer:
            # EOA path (backward-compatible with clients that don't send payer_address)
            try:
                msg = encode_defunct(text=message)
                recovered = Account.recover_message(msg, signature=signature_hex)
            except Exception as e:
                _record_sig_failure()
                return JsonResponse({'error': f'signature recovery failed: {e}'}, status=400)
            payer = to_checksum_address(recovered)
            # EOA recovery is chain-independent; record the settlement chain so
            # the settlement re-check has a concrete chain to re-recover on.
            validated_chain = chain_id
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
                        validated_chain = cid
                        # Snapshot the payer's code prefix on the validating
                        # chain. A later EIP-7702 revoke/redelegate (V75) changes
                        # this, so settlement can detect the delegation is no
                        # longer the one that authorized the quote.
                        try:
                            code = w3_for_sig.eth.get_code(to_checksum_address(claimed_payer))
                            payer_code_prefix = '0x' + bytes(code[:23]).hex()
                        except Exception as e:
                            log.warning('wc_create_quote: get_code snapshot failed for %s: %s',
                                        claimed_payer, e)
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
            signature=signature_hex, signed_message=message,
            sig_chain_id=validated_chain, payer_code_prefix=payer_code_prefix,
        )

        info['quote'] = quote
        # Append-only quote history. A buyer who re-quotes on the SAME payment
        # (e.g. switching wallet/token in the widget) would otherwise overwrite
        # `info['quote']` and lose the earlier attempts — leaving admin recovery
        # blind to which wallets/amounts were tried. Keep slim entries (no
        # signature blob, to bound info_data size), deduped by quote_id and
        # capped. Admin recovery + the manual-verify picker read this history.
        hist = list(info.get('quotes') or [])
        if not any(h.get('quote_id') == quote['quote_id'] for h in hist):
            hist.append({
                'quote_id': quote['quote_id'],
                'chain_id': quote['chain_id'],
                'symbol': quote['symbol'],
                'token_address': quote.get('token_address'),
                'intended_payer': quote['intended_payer'],
                'amount_raw': quote['amount_raw'],
                'created_at': quote['created_at'],
                'expires_at': quote['expires_at'],
            })
        info['quotes'] = hist[-25:]
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


def _revalidate_quote_signer(quote, settings_key):
    """Re-run the quote-time signer check at settlement. Closes the smart-wallet
    TOCTOU (V79 ERC-1271 toggle, V75 EIP-7702 revoke/redelegate): a validator
    that was only transiently authorized at quote time no longer validates here.
    EOA quotes re-recover cheaply (chain-independent); smart-wallet quotes
    re-eth_call isValidSignature on the chain that validated at quote time.
    Returns (ok: bool, reason: str)."""
    from pretix_eth.verification import verify_eth_payer_signature
    sig = quote.get('signature')
    msg = quote.get('signed_message')
    cid = quote.get('sig_chain_id')
    payer = quote.get('intended_payer')
    if not (sig and msg and cid and payer):
        # Legacy quote minted before signer binding existed — refuse to settle
        # rather than trust an unverifiable one-block snapshot.
        return False, 'quote has no bound signer (re-quote required)'
    try:
        w3 = _get_web3(int(cid), settings_key)
    except Exception as e:
        return False, f'signer re-check web3 error: {e}'
    try:
        if not verify_eth_payer_signature(w3=w3, payer=payer, message=msg, signature=sig):
            return False, 'signer no longer validates for this quote'
    except Exception as e:
        return False, f'signer re-check errored: {e}'
    # V75: if a code prefix was snapshotted (smart wallet / EIP-7702), require it
    # to be unchanged. A revoke or redelegate to a different validator changes
    # the 0xef0100||<impl> designator, so a quote bound at one delegation cannot
    # settle after the delegation moved.
    prefix = quote.get('payer_code_prefix')
    if prefix:
        try:
            code = w3.eth.get_code(to_checksum_address(payer))
            now_prefix = '0x' + bytes(code[:23]).hex()
        except Exception as e:
            return False, f'signer code re-check errored: {e}'
        if now_prefix != prefix:
            return False, 'payer code changed since quote (delegation revoked/redelegated)'
    return True, ''


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
        # 5s Retry-After: the tx is already mined, blocks come fast, and we
        # want the buyer's poll to resume promptly once a slot frees up.
        log.warning('wc_verify rejected: rate limit exceeded (ip) ip=%s', client_ip)
        return _rate_limited('rate limit exceeded (ip)', retry_after=5, ip=client_ip)
    if not _check_rate_limit(body['quote_id'], client_ip):
        log.warning('wc_verify rejected: rate limit exceeded quote_id=%s ip=%s', body.get('quote_id'), client_ip)
        return _rate_limited('rate limit exceeded', retry_after=5, quote_id=body.get('quote_id'), ip=client_ip)

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

        # V75/V79: re-establish the signer against the order's OWN stored quote
        # before settling. A validator that was only transiently authorized at
        # quote time (ERC-1271 toggle, EIP-7702 delegation) no longer validates.
        signer_ok, signer_reason = _revalidate_quote_signer(quote, settings_key)
        if not signer_ok:
            return _verify_bad(signer_reason, tx_hash=tx_hash)

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


def admin_fiat_blocked_items_js(request, **kwargs):
    """Serves the sync JS for the 'Items that block fiat payment' admin
    widget. Lives behind a plugin URL (rather than a collected static
    file) so it works on Pretix deployments using ManifestStaticFilesStorage
    without requiring `pretix rebuild` after install, and is allowed by
    strict admin CSP since it loads from the same origin (`'self'`)."""
    from pretix_eth.payment import _FIAT_BLOCKED_SYNC_JS
    return HttpResponse(
        _FIAT_BLOCKED_SYNC_JS,
        content_type='application/javascript; charset=utf-8',
    )


def order_redirect_js(request, **kwargs):
    """Serves a small JS that redirects the buyer from Pretix's stock
    order-detail page to the operator's configured frontend order URL
    (e.g. devcon.org). Matches the post-payment redirect that the wc_inject
    SuccessStep does for crypto orders, but fires for *any* payment
    provider (Stripe, bank transfer, etc.) — anywhere Pretix lands the
    buyer on its own order page after payment.

    Hooked into the page by the `wc_order_redirect_inject` html_head
    signal receiver in signals.py. Only injected when:
      - the buyer is on `event.order` (not /pay/, /cancel/, /change/, ...),
      - the order's payment status is PAID,
      - `payment_walletconnect_frontend_order_url_template` is configured
        on the event.

    Sourced as a `<script src="...">` (not inline) because Pretix's
    presale CSP typically forbids inline execution.
    """
    import json
    code = (request.GET.get('code') or '').strip()
    secret = (request.GET.get('secret') or '').strip()
    event = getattr(request, 'event', None)
    if not event or not code or not secret:
        return HttpResponse('// missing context', content_type='application/javascript; charset=utf-8')
    template = (event.settings.get('payment_walletconnect_frontend_order_url_template') or '').strip()
    if not template:
        return HttpResponse('// no redirect template configured', content_type='application/javascript; charset=utf-8')
    dest = template.replace('{code}', code).replace('{secret}', secret)
    # Allow http://, https://, or root-relative URLs — never javascript:,
    # data:, or any other scheme that could execute in the buyer's browser.
    # `http://` is intentionally allowed for localhost / dev environments;
    # for production deployments the operator's `frontend_order_url_template`
    # should be `https://…` anyway.
    if not (dest.startswith('https://') or dest.startswith('http://') or dest.startswith('/')):
        return HttpResponse('// invalid redirect destination', content_type='application/javascript; charset=utf-8')
    # No in-browser dedup needed: the signal receiver in signals.py only
    # injects this script on the URL that has `?thanks=yes`, which Pretix
    # appends exactly once (the post-payment landing redirect). Any
    # subsequent navigation back to `/order/<code>/<secret>/` (from the
    # email link, a bookmark, etc.) lacks that flag and never loads this
    # script, so we don't redirect — buyers can actually view their
    # Pretix order page when they want to.
    js = (
        '(function () {{ '
        'var dest = {dest}; '
        'setTimeout(function () {{ window.location.href = dest; }}, 2000); '
        '}})();'
    ).format(dest=json.dumps(dest))
    return HttpResponse(js, content_type='application/javascript; charset=utf-8')


class _VoucherPriceShim:
    """Duck-typed stand-in for a cart/order position so `apps._effective_fiat`
    can be reused at the item level (the redeem/catalog page has no cart
    position yet). Exposes just the attributes `_effective_fiat` reads:
    `voucher`, `listed_price`, `price_after_voucher` (and `price`). Keeps the
    displayed voucher discount identical to the one actually charged.
    """
    __slots__ = ('voucher', 'listed_price', 'price_after_voucher', 'price', 'variation', 'item')

    def __init__(self, voucher, listed_price, price_after_voucher):
        self.voucher = voucher
        self.listed_price = listed_price
        self.price_after_voucher = price_after_voucher
        self.price = price_after_voucher
        self.variation = None
        self.item = None


@csrf_exempt
@require_http_methods(['GET'])
def item_pricing(request, **kwargs):
    """Per-event item pricing map: `{items: [{id, default_price,
    fiat_price_usd, fiat_disabled}, ...]}`.

    Used by the wc_inject bundle to render dual prices ("$499 crypto /
    $999 fiat") on catalog and cart pages, since Pretix's stock templates
    only show `default_price`. Read-only, public; rate-limited per IP at
    the same rate as other buyer endpoints.

    Resolves the event from `request.event` (when called on the
    event-scoped URL) or from `?organizer=…&event=…` (root-level URL,
    used by the wc_inject bundle on main-domain deployments).

    Only active items are returned. Variations are NOT yet expanded —
    they inherit their parent's metadata for now; if per-variation fiat
    pricing becomes needed, extend this view to emit variation rows too.
    """
    client_ip = get_client_ip(request)
    if not _wc_buyer_rate_limit(client_ip, 'item_pricing'):
        return _rate_limited()

    event = getattr(request, 'event', None)
    if event is None:
        org_slug = (request.GET.get('organizer') or '').strip()
        ev_slug = (request.GET.get('event') or '').strip()
        if not (org_slug and ev_slug):
            return JsonResponse({'success': False, 'error': 'organizer and event are required'}, status=400)
        from pretix.base.models import Event
        with scopes_disabled():
            try:
                event = Event.objects.get(organizer__slug=org_slug, slug=ev_slug)
            except Event.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'event not found'}, status=404)

    def _truthy(v):
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ('true', 'yes', '1')

    with scopes_disabled():
        items = list(event.items.filter(active=True).values('id', 'default_price'))
        # Resolve meta_data for each item. ItemMetaValue access is per-item
        # so we batch via a single query and group in Python.
        from pretix.base.models import ItemMetaValue
        meta_rows = ItemMetaValue.objects.filter(
            item__event=event, item__active=True,
        ).select_related('property').values('item_id', 'property__name', 'value')
        per_item_meta: dict = {}
        for row in meta_rows:
            per_item_meta.setdefault(row['item_id'], {})[row['property__name']] = row['value']

        # Voucher-aware card pricing (redeem page: ?voucher=CODE). When the
        # buyer is redeeming a voucher we surface the discounted CARD price so
        # the fiat chip can show a strikethrough that mirrors the ETH one. The
        # discounted value is computed with the same `_effective_fiat` used for
        # the actual charge, so the display always matches what's billed.
        fiat_after_by_id: dict = {}
        from decimal import Decimal, InvalidOperation
        from .apps import _effective_fiat

        # Source 1 — redeem page (?voucher=CODE): no cart yet, so compute the
        # discounted card price for each item the voucher applies to.
        vcode = (request.GET.get('voucher') or '').strip()
        if vcode:
            from pretix.base.models import Voucher
            voucher = Voucher.objects.filter(event=event, code=vcode).first()
            if voucher is not None:
                item_objs = {i.pk: i for i in event.items.filter(active=True)}
                for it in items:
                    iid = it['id']
                    fiat_raw = (per_item_meta.get(iid, {}).get('fiat_price_usd') or '').strip()
                    item_obj = item_objs.get(iid)
                    if not fiat_raw or item_obj is None or not voucher.applies_to(item_obj):
                        continue
                    try:
                        listed = Decimal(str(it['default_price']))
                        fiat_dec = Decimal(fiat_raw)
                    except (InvalidOperation, ValueError, TypeError):
                        continue
                    shim = _VoucherPriceShim(voucher, listed, voucher.calculate_price(listed))
                    eff = _effective_fiat(shim, fiat_dec)
                    if eff != fiat_dec:
                        fiat_after_by_id[iid] = str(eff)

        # Source 2 — cart page: the voucher isn't in the URL there, so read the
        # buyer's actual cart positions (which carry the applied voucher /
        # discount) and compute the discounted card price straight from them
        # with the same _effective_fiat used to charge. Fills in items not
        # already resolved from a ?voucher= param.
        cart_id = None
        try:
            from pretix.presale.views.cart import get_or_create_cart_id
            cart_id = get_or_create_cart_id(request, create=False)
        except Exception:
            cart_id = None
        if not cart_id:
            try:
                cart_id = request.session.get('current_cart_event_{}'.format(event.pk))
            except Exception:
                cart_id = None
        if cart_id:
            from pretix.base.models import CartPosition
            cps = list(CartPosition.objects.filter(
                cart_id=cart_id, event=event,
            ).select_related('item', 'variation', 'voucher'))
            for cp in cps:
                iid = cp.item_id
                if iid in fiat_after_by_id:
                    continue
                fiat_raw = (per_item_meta.get(iid, {}).get('fiat_price_usd') or '').strip()
                if not fiat_raw:
                    continue
                try:
                    fiat_dec = Decimal(fiat_raw)
                except (InvalidOperation, ValueError, TypeError):
                    continue
                eff = _effective_fiat(cp, fiat_dec)
                if eff != fiat_dec:
                    fiat_after_by_id[iid] = str(eff)

    out = []
    for it in items:
        meta = per_item_meta.get(it['id'], {})
        fiat_raw = (meta.get('fiat_price_usd') or '').strip() or None
        out.append({
            'id': it['id'],
            'default_price': str(it['default_price']),
            'fiat_price_usd': fiat_raw,  # null when not overridden (fiat = default_price)
            'fiat_after_voucher': fiat_after_by_id.get(it['id']),  # null unless a voucher discounts the card price
            'fiat_disabled': _truthy(meta.get('fiat_disabled')),
        })
    response = JsonResponse({'items': out})
    # NEVER cache this response — not even the "generic" (empty-cart) variant.
    # `fiat_after_voucher` is cart-dependent (Source 2 reads the buyer's
    # CartPositions), but the endpoint URL is STABLE as the buyer moves
    # catalog -> redeem -> checkout. A `public, max-age=N` copy captured while
    # the cart was empty (fiat_after_voucher=null) gets replayed by the browser
    # / CDN on the following cart pages, so the card chip shows the full
    # undiscounted price (e.g. $999 instead of the voucher price) until a manual
    # reload forces revalidation. `no-store` guarantees every page re-fetches
    # and gets a cart-accurate price. The response is a small JSON fetched once
    # per page, so dropping the cache is cheap; correct pricing during a paid
    # sale is not negotiable.
    response['Cache-Control'] = 'private, no-store'
    return response


# Buyer-facing dual-price rendering bundle. Plain vanilla JS + a small
# injected stylesheet, no React or build step, so it ships as a single
# static response from the plugin URL and satisfies a strict `script-src
# 'self'` CSP.
#
# DOM contract (Pretix 5.x):
#   - Catalog item rows are `<article id="{prefix}item-{pk}">` (variations
#     get `item-{pk}-{var_pk}` — we only annotate the main row).
#   - Each item row has a `<div class="price">…</div>` inside its `.row`.
#   - Cart rows carry `data-article-id="item-{pk}"` on the rowgroup `<div>`
#     and render the line price in `.cart-row .price`.
#
# Per-item annotation logic:
#   - `fiat_disabled = true` → append a single warm-tinted "Ethereum only"
#     pill next to the existing price.
#   - `fiat_price_usd` set and different from `default_price` →
#       1. append a blue "Ethereum" pill next to the existing price
#       2. append a card-price line below with a gray "Card" pill + amount
#       3. if delta ≥ max($50, 10% of crypto), append a green
#          "Save $X with Ethereum" line.
#   - Otherwise (no metadata, or fiat = crypto) → no change.
#
# The ETH glyph icon is embedded as a base64 data URI (~4.6 KB inline) so
# the bundle is self-contained — avoids dependence on `collectstatic`
# under `ManifestStaticFilesStorage`, which has bitten this plugin before.
# The credit-card glyph is an inline SVG (~200 bytes).
_ETH_ICON_PNG_BASE64 = (
    'iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAYAAACM/rhtAAAABGdBTUEAALGPC/xhBQAAACBjSFJN'
    'AAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAARGVYSWZNTQAqAAAACAABh2kA'
    'BAAAAAEAAAAaAAAAAAADoAEAAwAAAAEAAQAAoAIABAAAAAEAAAAooAMABAAAAAEAAAAoAAAAAHrm'
    'ZqwAAAFZaVRYdFhNTDpjb20uYWRvYmUueG1wAAAAAAA8eDp4bXBtZXRhIHhtbG5zOng9ImFkb2Jl'
    'Om5zOm1ldGEvIiB4OnhtcHRrPSJYTVAgQ29yZSA2LjAuMCI+CiAgIDxyZGY6UkRGIHhtbG5zOnJk'
    'Zj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+CiAgICAgIDxy'
    'ZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiCiAgICAgICAgICAgIHhtbG5zOnhtcD0iaHR0cDov'
    'L25zLmFkb2JlLmNvbS94YXAvMS4wLyI+CiAgICAgICAgIDx4bXA6Q3JlYXRvclRvb2w+RmlnbWE8'
    'L3htcDpDcmVhdG9yVG9vbD4KICAgICAgPC9yZGY6RGVzY3JpcHRpb24+CiAgIDwvcmRmOlJERj4K'
    'PC94OnhtcG1ldGE+CgT/XMgAAAVySURBVFgJ5ZfbTxx1FMe/Mzs7uwNdoCAIWOSiRcG2toJBKthW'
    'bGI0RqrRpA/GxBjffDPx1b9FXohRk4a2qVHaalqk1WCIRZq0tOVWbsulC3ub289zZrm5BXZ3dh6a'
    '+HtYdmZ/8zufOZfvOUiff7Mo8AQv+Qlmc9D+X4BCArzOF289aAOyZHsK6RGggGnaqKuW8G5nIWzL'
    'Oz96A0g8kizhTJeG144E0VDjd4C9KEBPAHVDQsfRIF56LgDTAjpf0aAFZAgPHJk3oEV5V1oCvH8q'
    '4DjMovBWliloPRSEaedP6AGgjfdOBFFWomxGlL3Y0hxAVZmcN2RegIYJNNWreKNF24TjLxzaoCqh'
    'k+6zgXz86BpQEEXQL/DxaQ2KjwQwbVmWhIYDKuWlCoNd6nK5BjQM4GRbqmJ3su14jZT7+DENxYU+'
    'uE1HV4AWaV5VuYR3Ov4b2nTQVAHJJD1c3e4CnTsg2aHCxQddBSgqfDy06XdMU8LhF4Ooq1JcQeYM'
    'qJsCLU0qyQjLSjoOwF7jnJTWfxJ0rfpkp5D8ipSzNuYEyIVRpEn48C2qzk02QUYFVmM2puZs/DFi'
    'YPS+jnjChs9HvZk2WlTtNZUqXn5BJS+y/7NfW+KVxTOGIXDmlIbqCj/tFuQtgciawMoqEE3woCAh'
    'GpcwEzYxTrBVT0morVRQsi/lh/YjGsYmddov4Nt6wz0tZw1oUmgbnlVwul0j2RB4RGDLEYGkzq5M'
    'hdRxqkTG6VSTXmZ8WmBqNoHy/T7UViuOcJ9o1XDuSnQdajMMu0JmBcjCq1D+dJ8sQCQuEF4GQTKW'
    'vJlr6RY4BznEEDJmwwLzSwaKQzLqCbT+gB/3J83U7+kPpl1nBQj2Chm8cctACxkMaT7KLTbO0pHB'
    'CxugtHMlYmNg3iDPW05uprHseJkVIAWQpEXg5t8xjNzR0UEtrJk6hMKhJE9mWvwKCd3G4rJJcCYU'
    '6kCStHd9cuHJ5IW9d21Ypo7AtdfVFkB9jQ/nrq6h92IEEzMG5RsnPG/ckpaNxzjM3EEWlg2MjScR'
    'j1too3mxtJg6S4ZiluhhB3LjsD3/Uoht8tTQPybOvq3hy7P7oFM36emL4OKvUapKCyoVNgPx4mrm'
    'tOD798YTmA/raKxX8El3CAHaNxu2acDl9Mi8sgoxH+OjJJxbFug5H8NXn4Zw6HkVP/8ew6XrCYw+'
    '0HH8qIbWpoDj0SgX0koSqwT4zNN+vH6sAI11Ku5O6Lj+VwIKScz6u2QklHL5x53fWadc4jbX/WYB'
    'XQnMLJjouxrHwLCBilIfVBqzpuZMhEj72qkHHz4YRAFN10trJnovrGFplXLQqbCMbM6GrD3Iu/mt'
    'Vb+MC9cSaKxVnEKpKlfwxUchKhwDP/THMf7QxKvUBttooi4iWbEtmdJBoH8whsVHJvxKdmnv0NFH'
    'ToD8EKcXi3bP+TV8/VkxSkIsdkBzg4qDJOS37lrQgn4nwXkkU6lib4zEcfueTnDZBtY50vnI7XXW'
    'n+NhYHpeoPdS1AHZOI4BKvYrsGg+5SpViH2SdO/aEOUdC6mL5QqQ7agqCfdwElduUhPetrg/pzRM'
    'IGHY+GUgimSSdY8Bc4d0DcimZBLA7/sTlHf6NsTUVx4GfvszhocLtmvv8UmuAdkbPEpFYxa+7Ysj'
    'ntxSXu4wI2NJDN/WnR7+GH0ON/IATFnhqr4zYeJH8iRD84CwsGJS6GMkQtnr3W7MeQPywZyPlwcT'
    'GBrVnSq/PBhFJMq9dDez2d/PWWZ2OtoZJigpv/spijoapR5MW64kZaezPQHkg3lgCK/w3JfMO++2'
    'g3oQhK3jWEm4Z3u5PAX0EmzjLNchZjFOXykxTr+b37VrD26H2Q67/X5+aKmn/wU3GfeDPn/uywAA'
    'AABJRU5ErkJggg=='
)
# NOTE: ETH icon-container sourced from the Devcon Figma design (node
# 5160:7688 in file aQDeWGxyogMccLpHaONIHG) — a rounded purple tile
# with the Ethereum diamond glyph baked in, so the icon self-contains
# both the background color/radius and the glyph and needs no CSS
# wrapper. Resized to 40x40 (2x retina for the 20px display size).
# Regenerate with `sips -Z 40 <src.png> --out eth-container-40.png`.
_ETH_ICON_DATA_URI = 'data:image/png;base64,' + _ETH_ICON_PNG_BASE64

# Body uses sentinel placeholders that the view substitutes with
# JSON-encoded values at request time. Avoids Python f-string brace
# escaping in the JS body, keeping the JS readable.
_ITEM_PRICING_JS_BODY = r"""
(function () {
  'use strict';
  var ENDPOINT = __PED_ENDPOINT__;
  var ETH_ICON = __PED_ETH_ICON__;
  if (!ENDPOINT) return;

  // Design tokens from the Devcon Figma file (node 5111:7166): purple
  // tint for the ETH pill, neutral gray for the Fiat pill. Stacked
  // vertically below the existing price so the buyer's eye lands on the
  // price first, then sees the per-method clarification.
  // Icon-only layout: the payment method is conveyed purely by the
  // glyph, no text label. Cuts the row width in half compared to the
  // pill-with-label version, so the whole row (icon + price) always
  // fits on one line inside Pretix\'s native col-md-2 price column —
  // no more column-widening hack.
  //
  // Visual hierarchy:
  //   - ETH row gets a soft green pill background so the buyer\'s eye
  //     lands on it first (it\'s the recommended/cheaper price).
  //   - Fiat row is plain (no background) — visible but secondary.
  //   - Same green/18px/bold price text on both rows so the numbers
  //     read as directly comparable rather than "the real price and
  //     a footnote".
  //
  // Items whose crypto price equals their fiat price (or that have no
  // fiat metadata at all) don\'t get annotated — they render with the
  // default Pretix "new price" green treatment only.
  var CSS = (
    // Each row is right-aligned within Pretix\'s price column via
    // `margin-left:auto` on a fit-content width. Not flex-wrap because
    // with icons instead of labels, the content always fits.
    //
    // Padding lives on `.ped-row` (the shared base), not on the ETH
    // variant, so the ETH and Fiat rows have identical content boxes.
    // Only the visual chrome (background + border-radius) is added on
    // top for ETH. Result: icons and prices align vertically across
    // rows — the "$" in $499 lines up with the "$" in $999 whether the
    // ETH row has its green highlight or not.
    //
    // Sizing tokens sourced from the devcon.org Figma design (node
    // 5160:7687 in file aQDeWGxyogMccLpHaONIHG): 4px 6px padding,
    // 4px border-radius on the chip, 20px icon container, 6px gap.
    // The Pretix shop mirrors this styling but stacks the rows
    // vertically instead of horizontally (which is what devcon.org
    // does since it has more horizontal room per item card).
    '.ped-row{display:flex;align-items:center;gap:6px;width:fit-content;' +
      'margin-left:auto;margin-top:4px;padding:4px 6px}' +
    '.ped-row:first-child{margin-top:0}' +
    '.ped-row > p,.ped-row > strong{margin:0}' +
    // ETH row: soft green highlight. #dff0d8 is Bootstrap 3\'s
    // alert-success-bg — same green family as Pretix\'s built-in
    // `<ins>` price color, so the highlight visually reinforces the
    // "this is the crypto price" association. Padding comes from the
    // shared `.ped-row` rule above; border-radius matches Figma (4px).
    '.ped-eth-row{background:#dff0d8;border-radius:4px}' +
    // Icon container, fixed 20px per Figma\'s `size-[20px]` token.
    // Renders consistently regardless of surrounding font-size. The
    // 1px border-radius on the img/svg matches Figma\'s
    // `rounded-[1px]` — the ETH PNG has its own rounded corners baked
    // in, and this clips the Fiat SVG\'s baked-in rounded rect down
    // to the same 1px radius so both icons visually match.
    '.ped-icon{display:inline-flex;align-items:center;justify-content:center;' +
      'flex-shrink:0;width:20px;height:20px}' +
    '.ped-icon img,.ped-icon svg{width:20px;height:20px;display:block;' +
      'border-radius:1px}' +
    // Fiat amount uses Devcon\'s muted-foreground token (#594d73) per
    // the Figma design — signals "secondary payment method" against
    // the ETH row\'s highlighted accent-foreground. Same 18px/bold
    // weight as the ETH price so buyers still read them as directly
    // comparable, just with different chromatic emphasis.
    '.ped-fiat-amount{color:#594d73;font-size:18px;font-weight:bold;' +
      'line-height:1.2;font-variant-numeric:tabular-nums}' +
    // Relocated tax notice at the bottom (see moveTaxNoticeToBottom).
    '.ped-tax-line{text-align:right;margin-top:4px;line-height:1.2}' +
    // Explainer under the relabeled "Card payment fee" cart line.
    '.ped-fee-note{display:block;color:#777;font-size:0.78em;' +
      'font-weight:normal;line-height:1.3}' +
    // Promote the headline price to Pretix\'s "new price" treatment
    // (green/18px/bold from _event.scss `.price ins`) regardless of
    // whether (a) the item has a strikethrough original, (b) we
    // re-parented it into a `.ped-row` flex wrapper. Strikethrough
    // <del> children and tax <small> stay muted.
    '.price > p,.price > strong:first-child,' +
    '.price .ped-row > p,.price .ped-row > strong{' +
      'color:#3c763d;font-size:18px;font-weight:bold;line-height:1.2}' +
    // ETH row price gets Devcon\'s accent-foreground (#221144, dark
    // purple) instead of Pretix\'s ins-green, per Figma design token
    // `--general/accent-foreground`. Overrides the green base rule
    // above; more specific selector wins. Only affects the price text
    // when it\'s inside the ETH highlight chip — bare non-annotated
    // items and the Fiat row keep the green color.
    '.price .ped-eth-row > p,.price .ped-eth-row > strong{' +
      'color:#221144}' +
    '.price > p del,.price > p small,.price > small,' +
    '.price .ped-row > p del,.price .ped-row > p small,' +
    '.ped-tax-line small{' +
      'color:#777;font-size:0.78em;font-weight:normal}' +
    // Struck list price shown before the voucher-discounted amount on the
    // ETH and Fiat rows (list → discounted). Same gray treatment as Pretix\'s
    // own struck original price.
    '.ped-eth-row del.ped-eth-list,.ped-fiat-row del.ped-fiat-list{' +
      'color:#777;font-size:0.78em;font-weight:normal;' +
      'text-decoration:line-through;margin-right:3px}'
  );

  // Self-contained dollar-sign-in-tile icon for the Fiat pill. The dark
  // rounded square is baked into the SVG (Figma `Icon Container` style),
  // with a white $ glyph centered. Avoids the need for a second pill
  // background layer in CSS.
  var FIAT_SVG = (
    '<svg viewBox="0 0 14 14" fill="none" ' +
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<rect width="14" height="14" rx="2" fill="#594d73"/>' +
    '<g transform="translate(1 1)" fill="white">' +
    // Vertical bar of the $
    '<path d="M5.625 11V1C5.625 0.793 5.793 0.625 6 0.625C6.207 ' +
    '0.625 6.375 0.793 6.375 1V11C6.375 11.207 6.207 11.375 6 ' +
    '11.375C5.793 11.375 5.625 11.207 5.625 11Z"/>' +
    // S-curve of the $
    '<path d="M8.625 7.75C8.625 7.385 8.48 7.036 8.222 6.778C7.964 ' +
    '6.52 7.615 6.375 7.25 6.375H4.75C4.186 6.375 3.646 6.151 3.248 ' +
    '5.752C2.849 5.354 2.625 4.814 2.625 4.25C2.625 3.686 2.849 ' +
    '3.146 3.248 2.748C3.646 2.349 4.186 2.125 4.75 2.125H8.5C8.707 ' +
    '2.125 8.875 2.293 8.875 2.5C8.875 2.707 8.707 2.875 8.5 ' +
    '2.875H4.75C4.385 2.875 4.036 3.02 3.778 3.278C3.52 3.536 3.375 ' +
    '3.885 3.375 4.25C3.375 4.615 3.52 4.964 3.778 5.222C4.036 5.48 ' +
    '4.385 5.625 4.75 5.625H7.25C7.814 5.625 8.354 5.849 8.752 ' +
    '6.248C9.151 6.646 9.375 7.186 9.375 7.75C9.375 8.314 9.151 ' +
    '8.854 8.752 9.252C8.354 9.651 7.814 9.875 7.25 9.875H3C2.793 ' +
    '9.875 2.625 9.707 2.625 9.5C2.625 9.293 2.793 9.125 3 ' +
    '9.125H7.25C7.615 9.125 7.964 8.98 8.222 8.722C8.48 8.464 8.625 ' +
    '8.115 8.625 7.75Z"/>' +
    '</g></svg>'
  );

  function injectStyle() {
    if (document.getElementById('pretix-eth-dual-price-css')) return;
    var s = document.createElement('style');
    s.id = 'pretix-eth-dual-price-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function fmtMoney(v) {
    var n = parseFloat(v);
    if (!isFinite(n)) return v;
    var s = n.toFixed(2);
    return '$' + s.replace(/\.00$/, '').replace(/(\.[0-9])0$/, '$1');
  }

  // Icon builder — glyph only, no label. `kind` selects the asset:
  //   'eth'  → embedded Ethereum diamond PNG (data URI)
  //   'fiat' → inline dollar-sign-in-tile SVG (dark bg baked in)
  // The consumer wraps this icon inside a `.ped-row` next to the
  // matching price; the row itself carries the "which method?" signal
  // via its class (`.ped-eth-row` gets the green highlight).
  function buildIcon(kind) {
    var iconEl = document.createElement('span');
    iconEl.className = 'ped-icon';
    if (kind === 'eth') {
      var img = document.createElement('img');
      img.src = ETH_ICON;
      img.alt = '';
      iconEl.appendChild(img);
    } else {  // 'fiat'
      iconEl.innerHTML = FIAT_SVG;
    }
    return iconEl;
  }

  // Locate Pretix\'s native price element inside the .price column:
  //   - catalog (fragment_product_list.html): a <p> directly inside
  //     `.price` containing the amount text plus an inline tax <small>.
  //   - cart total (fragment_cart.html `.totalprice`): a <strong>
  //     directly inside `.price`, followed by a <br/> and a tax <small>.
  //   - cart per-unit (fragment_cart.html `.singleprice`): the amount is
  //     a BARE TEXT NODE with no wrapper element at all — wrap it in a
  //     <strong> on the fly so the row builder has an element to move.
  // Returns null when the structure doesn\'t match (rare, e.g. free or
  // ranged-price items) so the caller can fall back to non-inline
  // rendering without crashing.
  function findPriceElement(elem) {
    var el = elem.querySelector(':scope > p') ||
             elem.querySelector(':scope > strong');
    if (el) return el;
    for (var i = 0; i < elem.childNodes.length; i++) {
      var n = elem.childNodes[i];
      if (n.nodeType === Node.TEXT_NODE && /\d/.test(n.nodeValue)) {
        var wrap = document.createElement('strong');
        elem.insertBefore(wrap, n);
        wrap.appendChild(n);
        return wrap;
      }
    }
    return null;
  }

  // Remove any <br/> that\'s a direct child of .price. Pretix\'s cart
  // template uses <br/> as a separator between the price <strong> and
  // the tax <small>; once we relocate the <small> to the bottom and
  // move the <strong> into a flex row, the <br/> serves no purpose and
  // creates an unwanted blank line. Catalog has no <br/> here so this
  // is a no-op there.
  function dropOrphanBrs(elem) {
    var brs = elem.querySelectorAll(':scope > br');
    for (var i = 0; i < brs.length; i++) brs[i].remove();
  }

  function annotate(elem, info, isAddon) {
    if (elem.dataset.pedAnnotated === '1') return;

    // Only annotate items that have a payment-specific story:
    //   - `fiat_disabled` → mark with the ETH-highlight row (single row)
    //   - `fiat_price_usd` differs from crypto price → dual row layout
    //   - same price for both (fiat == crypto, or no override) → single row
    //     with BOTH icons before the price, so it\'s clear the amount applies
    //     to Ethereum and Card alike.
    var fiat = info.fiat_price_usd != null ? parseFloat(info.fiat_price_usd) : NaN;
    var def = parseFloat(info.default_price);
    var hasMeaningfulOverride = isFinite(fiat) && isFinite(def) && fiat !== def;
    // Same amount for both methods (and fiat not disabled) → both-icons row.
    var samePrice = !info.fiat_disabled && !hasMeaningfulOverride;

    // Free items ($0) have no payment-method distinction to communicate —
    // no icons at all (covers free tickets like "Core Devs" and $0 add-ons).
    if (!isFinite(def) || def <= 0) return;

    elem.dataset.pedAnnotated = '1';

    var priceEl = findPriceElement(elem);
    if (!priceEl) return;  // unexpected DOM shape; safer to no-op

    // When a voucher discounts this item but Pretix rendered only the final
    // price (the cart does this; the redeem page strikes the original itself),
    // prepend the struck list price so our chip matches Pretix\'s original→
    // discounted treatment. Skipped when Pretix already shows a <del>.
    var discounted = info.fiat_after_voucher != null;
    var alreadyStruck = !!(priceEl.querySelector && priceEl.querySelector('del'));
    function prependStruckList(row) {
      if (discounted && !alreadyStruck && isFinite(def)) {
        var d = document.createElement('del');
        d.className = 'ped-eth-list';
        d.textContent = fmtMoney(def);
        row.appendChild(d);
      }
    }

    // Same price for both methods: one neutral row, both icons, single price.
    // No green highlight — neither method is cheaper, so it shouldn\'t imply one.
    // Skipped for add-ons: the dual-icon hint would just clutter secondary
    // rows (shirts, chess sets, etc.) — leave them at Pretix\'s plain price.
    if (samePrice) {
      if (isAddon) return;
      var bothRow = document.createElement('div');
      bothRow.className = 'ped-row ped-both-row';
      priceEl.parentNode.insertBefore(bothRow, priceEl);
      bothRow.appendChild(buildIcon('eth'));
      bothRow.appendChild(buildIcon('fiat'));
      prependStruckList(bothRow);
      bothRow.appendChild(priceEl);
      dropOrphanBrs(elem);
      moveTaxNoticeToBottom(elem);
      return;
    }

    // ETH row (fiat_disabled or dual-priced): wraps Pretix\'s native price
    // element with the ETH icon on the left, in a soft-green highlighted chip.
    var ethRow = document.createElement('div');
    ethRow.className = 'ped-row ped-eth-row';
    priceEl.parentNode.insertBefore(ethRow, priceEl);
    ethRow.appendChild(buildIcon('eth'));
    prependStruckList(ethRow);
    ethRow.appendChild(priceEl);

    // Fiat row (only for dual-priced items — skipped when fiat is
    // disabled for this item). No highlight, secondary weight.
    if (!info.fiat_disabled) {
      var fiatRow = document.createElement('div');
      fiatRow.className = 'ped-row ped-fiat-row';
      fiatRow.appendChild(buildIcon('fiat'));
      var fiatAfter = info.fiat_after_voucher != null ? parseFloat(info.fiat_after_voucher) : NaN;
      if (isFinite(fiatAfter) && fiatAfter !== fiat) {
        // Voucher discounts the card price too: show the list price struck
        // through, then the discounted price — mirrors the ETH row.
        var del = document.createElement('del');
        del.className = 'ped-fiat-list';
        del.textContent = fmtMoney(fiat);
        fiatRow.appendChild(del);
        var amtD = document.createElement('span');
        amtD.className = 'ped-fiat-amount';
        amtD.textContent = fmtMoney(fiatAfter);
        fiatRow.appendChild(amtD);
      } else {
        var amt = document.createElement('span');
        amt.className = 'ped-fiat-amount';
        amt.textContent = fmtMoney(fiat);
        fiatRow.appendChild(amt);
      }
      elem.appendChild(fiatRow);
    }

    dropOrphanBrs(elem);
    moveTaxNoticeToBottom(elem);
  }

  // Pretix renders the "incl. 18% GST" notice as a <small> next to the
  // price — inside a <p> in fragment_product_list.html, as a direct
  // child of .price in fragment_cart.html. By default that puts it
  // above our pills. Detach it and re-append below so the visual order
  // becomes:  price → ETH/Fiat pills → tax notice.
  // No-op when no tax small is present (e.g. tax-exempt items) or when
  // it's already been moved (idempotency guard via a marker class).
  function moveTaxNoticeToBottom(elem) {
    var smalls = elem.querySelectorAll('small');
    for (var i = 0; i < smalls.length; i++) {
      var s = smalls[i];
      if (s.classList.contains('ped-tax-moved')) continue;
      var txt = (s.textContent || '').trim();
      // Match Pretix's "incl. X% TaxName" / "plus X% TaxName" output.
      // Allowing both forms in case the event uses net-price display.
      if (!/^(incl\.|plus)/i.test(txt)) continue;
      s.classList.add('ped-tax-moved');
      var line = document.createElement('div');
      line.className = 'ped-tax-line';
      // appendChild moves the node from its current parent.
      line.appendChild(s);
      elem.appendChild(line);
    }
  }

  // Detect whether a row is an add-on so the same-price dual-icon hint can be
  // skipped. Two contexts:
  //   - cart: Pretix marks add-on lines with `.addon-signifier` (the "+").
  //   - add-on SELECTION step ("Additional options for …"): items are nested
  //     under `.panel-group.addons` / `.cross-selling` panels.
  function isAddonRow(el) {
    if (el.querySelector && el.querySelector('.addon-signifier')) return true;
    return !!(el.closest && el.closest('.addons, .cross-selling'));
  }

  function applyToDocument(byId) {
    // Catalog: <article id="…item-{pk}">. We only annotate the main row;
    // variations under the same item inherit the parent's metadata.
    document.querySelectorAll('article[id]').forEach(function (article) {
      var m = article.id.match(/item-(\d+)$/);
      if (!m) return;
      var info = byId[parseInt(m[1], 10)];
      if (!info) return;
      var priceDiv = article.querySelector(':scope > .row .price') ||
                     article.querySelector('.price');
      if (priceDiv) annotate(priceDiv, info, isAddonRow(article));
    });
    // Cart: rowgroup with data-article-id="item-{pk}" or "item-{pk}-{var}".
    // Annotate the per-unit `.singleprice` cell — `fiat_price_usd` is a
    // per-unit amount, so pairing it with the unit price stays correct at
    // any quantity (the `.totalprice` cell keeps the plain line total).
    // Fall back to the first `.price` for cart variants that render
    // without a singleprice column.
    document.querySelectorAll('[data-article-id^="item-"]').forEach(function (row) {
      var m = row.getAttribute('data-article-id').match(/^item-(\d+)/);
      if (!m) return;
      var info = byId[parseInt(m[1], 10)];
      if (!info) return;
      var priceDiv = row.querySelector('.singleprice.price') || row.querySelector('.price');
      if (priceDiv) annotate(priceDiv, info, isAddonRow(row));
    });
  }

  // Strip trailing ".00" from any money-shaped text node inside a
  // .price column. Pretix\'s Django `money` filter always renders with
  // 2 decimals, so a $349 ticket shows as "$349.00" — visually noisy
  // when there\'s no fractional cents to communicate. Regex matches a
  // digit immediately followed by ".00" and a word boundary, so:
  //   - "$349.00" → "$349"       ✓
  //   - "$12.50" → "$12.50"      ✓ (non-zero cents preserved)
  //   - "$1,043.00" → "$1,043"   ✓
  //   - "18.00%" → "18%"         ✓ (also cleans the tax notice)
  // Runs on every .price div on the page, so it covers the catalog,
  // cart line items, cart totals, and any struck-through <del> price.
  // Works across the DOM tree via TreeWalker so it reaches text nodes
  // nested inside <p>/<strong>/<ins>/<del>.
  function stripPriceTrailingZeros() {
    var priceDivs = document.querySelectorAll('.price');
    priceDivs.forEach(function (pd) {
      var walker = document.createTreeWalker(pd, NodeFilter.SHOW_TEXT, null, false);
      var toUpdate = [];
      var n;
      while ((n = walker.nextNode())) {
        if (/\d\.00\b/.test(n.nodeValue)) toUpdate.push(n);
      }
      toUpdate.forEach(function (node) {
        node.nodeValue = node.nodeValue.replace(/(\d)\.00\b/g, '$1');
      });
    });
  }

  // Relabel Pretix\'s generic "Payment fee" cart line. The fee is the
  // difference between the ETH-denominated base price and the card
  // price (e.g. $499 base → $999 via card adds a $500 fee line), not a
  // processing surcharge on top — say so where the buyer decides.
  // Display-only: invoices, emails, and the organizer backend keep
  // Pretix\'s standard "Payment fee" naming, which is what accounting
  // documents should carry. Matched on the English label; other shop
  // locales fall back to the stock label untouched.
  function relabelPaymentFee() {
    document.querySelectorAll('.cart-row strong').forEach(function (el) {
      if (el.dataset.pedFeeRelabeled === '1') return;
      if ((el.textContent || '').trim() !== 'Payment fee') return;
      // Skip the price cell — it also renders its amount in a <strong>.
      if (el.closest('.price')) return;
      el.dataset.pedFeeRelabeled = '1';
      el.textContent = 'Card payment fee';
      var note = document.createElement('small');
      note.className = 'ped-fee-note';
      note.textContent = 'difference between the ETH price and the card price';
      el.parentNode.appendChild(note);
    });
  }

  function load() {
    injectStyle();
    // Strip ".00" before we start moving elements around; keeps text
    // node handling simple and applies to every row regardless of
    // whether the pricing JSON fetch succeeds.
    stripPriceTrailingZeros();
    relabelPaymentFee();
    // Forward the redeem-page voucher (?voucher=CODE) so the endpoint can
    // return the discounted card price for the fiat chip's strikethrough.
    var ep = ENDPOINT;
    var vm = location.search.match(/[?&]voucher=([^&#]+)/);
    if (vm) ep += (ep.indexOf('?') === -1 ? '?' : '&') + 'voucher=' + vm[1];
    fetch(ep, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.items) return;
        var byId = {};
        data.items.forEach(function (it) { byId[it.id] = it; });
        applyToDocument(byId);
      })
      .catch(function () {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
"""


@require_http_methods(['GET'])
def item_pricing_js(request, **kwargs):
    """Serve the buyer-side dual-price rendering JS for the current event.

    Loaded via an `html_head` injection on Pretix's catalog and cart pages
    (see `pretix_eth.signals.inject_item_pricing`). The script fetches
    `plugin/wc/item-pricing/` for the event and DOM-annotates each item
    row with pills indicating Ethereum vs Card pricing, plus an optional
    "Save $X with Ethereum" callout for items with a meaningful fiat
    markup.

    Both the endpoint URL and the ETH icon data URI are substituted into
    the JS body at request time so the JS body itself is a static string
    constant (no Python f-string brace escaping needed).
    """
    import json
    event = getattr(request, 'event', None)
    endpoint_url = '/plugin/wc/item-pricing/'
    if event is not None:
        try:
            from pretix.multidomain.urlreverse import eventreverse
            endpoint_url = eventreverse(event, 'plugins:pretix_eth:wc_item_pricing')
        except Exception:
            pass
    js = (
        _ITEM_PRICING_JS_BODY
        .replace('__PED_ENDPOINT__', json.dumps(endpoint_url))
        .replace('__PED_ETH_ICON__', json.dumps(_ETH_ICON_DATA_URI))
    )
    return HttpResponse(js, content_type='application/javascript; charset=utf-8')
