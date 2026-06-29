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

    out = []
    for it in items:
        meta = per_item_meta.get(it['id'], {})
        fiat_raw = (meta.get('fiat_price_usd') or '').strip() or None
        out.append({
            'id': it['id'],
            'default_price': str(it['default_price']),
            'fiat_price_usd': fiat_raw,  # null when not overridden (fiat = default_price)
            'fiat_disabled': _truthy(meta.get('fiat_disabled')),
        })
    response = JsonResponse({'items': out})
    # Short cache: item config doesn't change every second, but admins
    # editing prices want to see updates within a minute. CDN can override.
    response['Cache-Control'] = 'public, max-age=60'
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
    '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'
    'sAPwOeoAAAAASUVORK5CYII='
)
# NOTE: The exact base64 above was generated from
# pretix_eth/static/wc_inject/icons/tokens/eth.png at build time and is
# the same image the wc_inject bundle uses to represent ETH. Regenerate
# with `base64 < eth.png` if the source PNG changes.
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

  var CSS = (
    '.ped-pill{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;' +
      'border-radius:999px;font-size:0.72em;font-weight:600;line-height:1.3;' +
      'vertical-align:middle;white-space:nowrap;letter-spacing:0.01em}' +
    '.ped-pill .ped-icon{width:12px;height:12px;display:inline-flex;' +
      'align-items:center;justify-content:center;flex-shrink:0}' +
    '.ped-pill .ped-icon img,.ped-pill .ped-icon svg{width:12px;height:12px;' +
      'display:block}' +
    '.ped-pill.ped-eth{background-color:rgba(98,126,234,0.14);color:#2f3aa0}' +
    '.ped-pill.ped-card{background-color:rgba(0,0,0,0.06);color:#555}' +
    '.ped-pill.ped-only{background-color:rgba(217,119,6,0.14);color:#b45309}' +
    '.ped-eth-inline{margin-left:6px}' +
    '.ped-card-line{display:flex;justify-content:flex-end;align-items:center;' +
      'gap:6px;font-size:0.9em;color:#777;margin-top:4px}' +
    '.ped-card-line .ped-card-amount{font-variant-numeric:tabular-nums}' +
    '.ped-save-line{margin-top:3px;font-size:0.78em;color:#047857;' +
      'text-align:right;font-style:italic}' +
    '[data-article-id^="item-"] .ped-card-line,' +
    '[data-article-id^="item-"] .ped-save-line{justify-content:flex-end}'
  );

  var CARD_SVG = (
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
    '<path d="M20 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z"/>' +
    '</svg>'
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

  function buildPill(kind) {
    var pill = document.createElement('span');
    pill.className = 'ped-pill ped-' + kind;
    var iconEl = document.createElement('span');
    iconEl.className = 'ped-icon';
    if (kind === 'eth' || kind === 'only') {
      var img = document.createElement('img');
      img.src = ETH_ICON;
      img.alt = '';
      iconEl.appendChild(img);
    } else if (kind === 'card') {
      iconEl.innerHTML = CARD_SVG;
    }
    pill.appendChild(iconEl);
    var lbl = document.createElement('span');
    lbl.textContent = (kind === 'eth') ? 'Ethereum' :
                      (kind === 'card') ? 'Card' :
                      (kind === 'only') ? 'Ethereum only' : '';
    pill.appendChild(lbl);
    return pill;
  }

  function annotate(elem, info) {
    if (elem.dataset.pedAnnotated === '1') return;

    // Only annotate items that have something payment-specific to say.
    // Items without an override and without fiat_disabled (free swag,
    // comps, items where fiat == crypto) get no pill — the listed price
    // is what every buyer pays, regardless of method. Adding an
    // "Ethereum" pill on those would falsely imply a per-item payment
    // choice (payment method is actually a cart-level decision).
    var fiat = info.fiat_price_usd != null ? parseFloat(info.fiat_price_usd) : NaN;
    var def = parseFloat(info.default_price);
    var hasMeaningfulOverride = isFinite(fiat) && isFinite(def) && fiat !== def;
    if (!info.fiat_disabled && !hasMeaningfulOverride) return;

    elem.dataset.pedAnnotated = '1';

    if (info.fiat_disabled) {
      var only = buildPill('only');
      only.classList.add('ped-eth-inline');
      elem.appendChild(only);
      return;
    }

    // Has a meaningful fiat override: tag the existing crypto price with
    // an "Ethereum" pill and append the card-price line below.
    var ethPill = buildPill('eth');
    ethPill.classList.add('ped-eth-inline');
    elem.appendChild(ethPill);

    var cardLine = document.createElement('div');
    cardLine.className = 'ped-card-line';
    cardLine.appendChild(buildPill('card'));
    var amt = document.createElement('span');
    amt.className = 'ped-card-amount';
    amt.textContent = fmtMoney(fiat);
    cardLine.appendChild(amt);
    elem.appendChild(cardLine);

    // Savings callout — only when the delta is meaningful, so cheap items
    // (where +$2 to fiat is technically a "saving" but reads as noise)
    // don't clutter the catalog.
    var delta = fiat - def;
    var threshold = Math.max(50, def * 0.10);
    if (delta >= threshold) {
      var save = document.createElement('div');
      save.className = 'ped-save-line';
      save.textContent = 'Save ' + fmtMoney(delta) + ' with Ethereum';
      elem.appendChild(save);
    }
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
      if (priceDiv) annotate(priceDiv, info);
    });
    // Cart: rowgroup with data-article-id="item-{pk}" or "item-{pk}-{var}".
    document.querySelectorAll('[data-article-id^="item-"]').forEach(function (row) {
      var m = row.getAttribute('data-article-id').match(/^item-(\d+)/);
      if (!m) return;
      var info = byId[parseInt(m[1], 10)];
      if (!info) return;
      var priceDiv = row.querySelector('.price');
      if (priceDiv) annotate(priceDiv, info);
    });
  }

  function load() {
    injectStyle();
    fetch(ENDPOINT, { credentials: 'same-origin' })
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
