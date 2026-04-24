"""HTTP endpoints for the WalletConnect payment flow."""
import asyncio
import json
import logging
import os
import re
import secrets
import time
from decimal import Decimal

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_scopes import scopes_disabled
from web3 import Web3

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address

from pretix.base.models import Order
from pretix_eth.chains import (
    SUPPORTED_CHAINS, ALL_SYMBOLS, CHAIN_METADATA,
    TOKEN_CONTRACTS, is_supported,
)
from pretix_eth.models import WCPaymentAttempt
from pretix_eth.pricing import build_quote, fetch_eth_price_usd
from pretix_eth.payment import WalletConnectPayment
from pretix_eth.rpc import get_rpc_url
from pretix_eth.verification import verify_erc20_transfer, verify_native_eth

log = logging.getLogger(__name__)

RATE_LIMIT_PER_MIN = int(os.environ.get('WC_VERIFY_RATE_LIMIT_PER_MIN', '10'))


def _check_rate_limit(quote_id: str, ip: str) -> bool:
    """Return False if caller has exceeded WC_VERIFY_RATE_LIMIT_PER_MIN for this quote+IP pair."""
    key = f'wc_verify_rl:{quote_id}:{ip}'
    count = cache.get(key, 0)
    if count >= RATE_LIMIT_PER_MIN:
        return False
    cache.set(key, count + 1, timeout=60)
    return True


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
def payment_options(request):
    provider = _get_provider_for_event(request)
    if provider is None:
        return JsonResponse({'error': 'event not found'}, status=404)

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

    # ETH availability (dual-oracle)
    eth_available = True
    eth_disabled_reason = None
    if 'ETH' in enabled_tokens:
        try:
            result = asyncio.run(fetch_eth_price_usd())
            if result is None:
                eth_available = False
                eth_disabled_reason = 'oracle_unavailable_or_diverged'
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
        'receive_address': receive_address,
        'chain_metadata': {str(cid): CHAIN_METADATA[cid] for cid in enabled_chains},
    })


CHALLENGE_TTL = 600  # 10 min


@csrf_exempt
@require_http_methods(['POST'])
def challenge(request):
    """Issue a signed-message challenge that the user's wallet must sign,
    proving ownership of the address that will pay."""
    body = _read_body(request)

    required = ('order_code', 'order_secret', 'organizer', 'event')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({'error': f'missing fields: {missing}'}, status=400)

    with scopes_disabled():
        try:
            order = Order.objects.get(
                code=body['order_code'],
                event__slug=body['event'],
                event__organizer__slug=body['organizer'],
            )
        except Order.DoesNotExist:
            return JsonResponse({'error': 'order not found'}, status=404)

        if order.secret != body['order_secret']:
            return JsonResponse({'error': 'invalid secret'}, status=403)

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
        payment.info_data = info
        payment.save()

    return JsonResponse({
        'nonce': nonce,
        'message': message,
        'expires_at': expires_at,
    })


@csrf_exempt
@require_http_methods(['POST'])
def create_quote(request):
    """Recover the payer from a SIWE-lite signature, validate the challenge,
    build a quote, and persist it to the pending payment's info_data."""
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

    with scopes_disabled():
        try:
            order = Order.objects.get(
                code=body['order_code'],
                event__slug=body['event'],
                event__organizer__slug=body['organizer'],
            )
        except Order.DoesNotExist:
            return JsonResponse({'error': 'order not found'}, status=404)

        if order.secret != body['order_secret']:
            return JsonResponse({'error': 'invalid secret'}, status=403)

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

        if sig_len_bytes == 65 and not claimed_payer:
            # EOA path (backward-compatible with clients that don't send payer_address)
            try:
                msg = encode_defunct(text=message)
                recovered = Account.recover_message(msg, signature=signature_hex)
            except Exception as e:
                return JsonResponse({'error': f'signature recovery failed: {e}'}, status=400)
            payer = to_checksum_address(recovered)
        else:
            if not claimed_payer:
                return JsonResponse({
                    'error': (
                        'payer_address is required for smart-wallet signatures '
                        f'(got {sig_len_bytes}-byte signature, not a 65-byte ECDSA)'
                    ),
                }, status=400)
            provider = WalletConnectPayment(order.event)
            settings_key = provider.settings.get('alchemy_api_key', default=None)
            from pretix_eth.verification import verify_eth_payer_signature
            # personal_sign signatures don't embed a chain_id, so for the
            # ownership check we can use any chain where the smart wallet
            # is deployed. Coinbase/Base Smart Wallet uses CREATE2 with a
            # shared factory + same init data across chains → same address,
            # same owners everywhere. If validation fails on the payment
            # chain (often because the wallet is counterfactual there),
            # retry on Base — CSW's native chain, where it's almost always
            # deployed once the user has ever touched their CSW account.
            fallback_chain_ids = [chain_id]
            if chain_id != 8453:
                fallback_chain_ids.append(8453)
            sig_ok = False
            for cid in fallback_chain_ids:
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
                return JsonResponse({
                    'error': (
                        'signature does not validate against payer_address '
                        '(checked chain(s): ' + ','.join(str(c) for c in fallback_chain_ids) + ')'
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
        payment.info_data = info
        payment.save()

    return JsonResponse(quote)


@csrf_exempt
@require_http_methods(['POST'])
def verify(request):
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
        return JsonResponse({'error': f'missing fields: {missing}'}, status=400)

    client_ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR', 'unknown')
    if not _check_rate_limit(body['quote_id'], client_ip):
        return JsonResponse({'error': 'rate limit exceeded'}, status=429)

    tx_hash = body['tx_hash']
    if not _TX_HASH_RE.match(tx_hash):
        return JsonResponse({'error': 'invalid tx_hash format'}, status=400)

    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'error': 'invalid chain_id'}, status=400)

    # Fail fast on one-time tx_hash check
    if WCPaymentAttempt.objects.filter(tx_hash=tx_hash, state='completed').exists():
        return JsonResponse({'error': 'tx already used for a completed order'}, status=400)

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
            return JsonResponse({'error': 'order not found'}, status=404)
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
            return JsonResponse({'error': 'quote not found'}, status=404)

        quote = payment.info_data['quote']

        if chain_id != quote['chain_id']:
            return JsonResponse({'error': 'chain_id mismatch'}, status=400)

        if time.time() > quote['expires_at']:
            return JsonResponse({'error': 'quote expired'}, status=400)

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
            return JsonResponse({'verified': False, 'error': vr.error}, status=400)

        # Atomic claim: unique constraint on tx_hash prevents race
        try:
            with transaction.atomic():
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
                payment.confirm()
        except IntegrityError:
            return JsonResponse({'error': 'tx already used (race)'}, status=409)

    return JsonResponse({
        'verified': True,
        'block_number': vr.block_number,
        'order_code': order.code,
    })
