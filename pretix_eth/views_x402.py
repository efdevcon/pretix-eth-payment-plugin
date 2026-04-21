# pretix_eth/views_x402.py
"""x402 endpoints: purchase, payment-options, relayer, verify."""
import json
import logging
import re
import secrets
from datetime import timedelta
from decimal import Decimal

from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_scopes import scopes_disabled
from web3 import Web3

from pretix_eth.chains import SUPPORTED_CHAINS, get_token_contract
from pretix_eth.payment import WalletConnectPayment
from pretix_eth.pricing import usd_to_token_raw
from pretix_eth.rpc import get_rpc_url
from pretix_eth.verification import verify_erc20_transfer, verify_native_eth
from pretix_eth.x402 import ticketstore
from pretix_eth.x402.auth import require_pretix_token
from pretix_eth.x402.balances import fetch_balances_for_wallet
from pretix_eth.x402.config import resolve_relayer_pk
from pretix_eth.x402.nonce import generate_nonce_bytes32
from pretix_eth.x402.pretix_client import create_pretix_order, confirm_x402_payment
from pretix_eth.x402.gas import GasConditionError
from pretix_eth.x402.relayer import (
    execute_transfer_with_authorization,
    RelayerError,
    RelayerInsufficientFundsError,
    RelayerResult,
)
from pretix_eth.x402.typed_data import build_transfer_authorization_typed_data

log = logging.getLogger(__name__)

_TX_HASH_RE = re.compile(r'^0x[a-fA-F0-9]{64}$')


_CAMEL_TO_SNAKE = {
    'paymentReference': 'payment_reference',
    'intendedPayer': 'intended_payer',
    'chainId': 'chain_id',
    'txHash': 'tx_hash',
    'tokenAddress': 'token_address',
    'walletAddress': 'wallet_address',
    'adminAddress': 'admin_address',
    'refundTxHash': 'refund_tx_hash',
    'challengeNonce': 'challenge_nonce',
    'challengeSignature': 'challenge_signature',
    'ethPayerSignature': 'ethPayerSignature',  # keep this one camelCase (matches frontend)
}


def _read_body(request) -> dict:
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return {}
    # Accept both camelCase (from devcon frontend) and snake_case at the top level
    if isinstance(body, dict):
        for camel, snake in _CAMEL_TO_SNAKE.items():
            if camel in body and snake not in body:
                body[snake] = body[camel]
    return body


@scopes_disabled()
def _get_event(org_slug: str, event_slug: str):
    from pretix.base.models import Event
    try:
        return Event.objects.get(slug=event_slug, organizer__slug=org_slug)
    except Event.DoesNotExist:
        return None


def _get_provider(event):
    return WalletConnectPayment(event)


def _addr_eq(a: str, b: str) -> bool:
    return (a or '').lower() == (b or '').lower()


def _w3_for_chain(chain_id: int, alchemy_key):
    url = get_rpc_url(chain_id, settings_key=alchemy_key)
    return Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))


NATIVE_ETH_PLACEHOLDER = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'

CHAIN_NAMES = {
    1: 'Ethereum', 10: 'Optimism', 137: 'Polygon', 8453: 'Base', 42161: 'Arbitrum',
}


# ---------------------------------------------------------------------------
# Task 21: payment_options
# ---------------------------------------------------------------------------


def _build_asset_caip(chain_id: int, token_address: str) -> str:
    return f'eip155:{chain_id}/erc20:{token_address}'


def _supported_assets_for_event(provider) -> list:
    """Build the list of supported (chain, token) combos from plugin settings.
    Mirrors devcon's SUPPORTED_ASSETS_MAINNET shape."""
    from pretix_eth.chains import TOKEN_CONTRACTS
    enabled_chains = [
        cid for cid in SUPPORTED_CHAINS
        if str(provider.settings.get(f'chain_{cid}', default='True')).lower() in ('true', '1', 'yes')
    ]
    enabled_symbols = set()
    for sym in ('USDC', 'USDT0', 'ETH'):
        if str(provider.settings.get(f'token_{sym}', default='True')).lower() in ('true', '1', 'yes'):
            enabled_symbols.add(sym)

    assets = []
    for cid in enabled_chains:
        if 'ETH' in enabled_symbols:
            assets.append({
                'chainId': cid,
                'symbol': 'ETH',
                'name': 'Ether',
                'chain': CHAIN_NAMES[cid],
                'tokenAddress': NATIVE_ETH_PLACEHOLDER,
                'decimals': 18,
            })
        for (c_id, symbol), info in TOKEN_CONTRACTS.items():
            if c_id != cid or symbol not in enabled_symbols:
                continue
            assets.append({
                'chainId': cid,
                'symbol': symbol,
                'name': 'USD Coin' if symbol == 'USDC' else 'USDT0',
                'chain': CHAIN_NAMES[cid],
                'tokenAddress': info['address'],
                'decimals': info['decimals'],
            })
    return assets


def _typed_data_to_json(td: dict) -> dict:
    """Serialize EIP-712 typed data for JSON transport (BigInt-safe)."""
    msg = td['message']
    return {
        'domain': td['domain'],
        'types': td['types'],
        'primaryType': td['primaryType'],
        'message': {
            **msg,
            'value': str(msg.get('value', '')),
            'validAfter': str(msg.get('validAfter', 0)),
            'validBefore': str(msg.get('validBefore', 0)),
        },
    }


@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_token
def payment_options(request: HttpRequest):
    """Return rich PaymentOption[] matching the devcon frontend contract:
    - asset (CAIP), symbol, name, chain, chainId (CAIP string)
    - amount (raw token units), balance, sufficient
    - signingRequest: EIP-712 typed data for USDC/USDT0 gasless, eth_sendTransaction params for ETH
    - priceUsd (for ETH), expiresAt
    """
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer

    payment_ref = body.get('payment_reference') or body.get('paymentReference')
    wallet = body.get('wallet_address') or body.get('walletAddress')
    if not payment_ref or not wallet:
        return JsonResponse({'error': 'paymentReference and walletAddress are required'}, status=400)

    with scopes_disabled():
        pending = ticketstore.get_pending_order(event=event, payment_reference=payment_ref)
    if pending is None:
        return JsonResponse({'error': 'Payment reference not found or expired'}, status=404)
    if int(pending.expires_at.timestamp()) < int(timezone.now().timestamp()):
        return JsonResponse({'error': 'Payment has expired'}, status=400)

    provider = _get_provider(event)
    alchemy_key = provider.settings.get('alchemy_api_key', default=None) or None
    recipient = provider.settings.get('payment_recipient')
    if not recipient:
        return JsonResponse({'error': 'merchant recipient not configured'}, status=500)
    expires_at = int(pending.expires_at.timestamp())

    # Fetch ETH price (may be None if oracles diverge — ETH options will be skipped)
    import asyncio
    from pretix_eth.pricing import fetch_eth_price_usd
    try:
        eth_price_result = asyncio.run(fetch_eth_price_usd())
        eth_price_usd = eth_price_result.price if eth_price_result else None
    except Exception:
        eth_price_usd = None

    # Fetch wallet balances across all enabled chains
    enabled_chain_ids = sorted({
        a['chainId'] for a in _supported_assets_for_event(provider)
    })
    raw_balances = fetch_balances_for_wallet(
        wallet=wallet, chain_ids=enabled_chain_ids, alchemy_key=alchemy_key,
    )
    # Map for lookup: (chain_id, symbol, token_address_lower) -> balance_raw
    bal_map = {}
    for b in raw_balances:
        key_addr = (b.get('token_address') or NATIVE_ETH_PLACEHOLDER).lower()
        bal_map[(b['chain_id'], b['symbol'], key_addr)] = b['balance']

    # Compute amounts
    total_usd = pending.total_usd
    usdc_amount_raw = int(total_usd * (10 ** 6))  # USDC/USDT0 both 6 decimals
    eth_amount_wei = None
    if eth_price_usd is not None:
        # Ceiling division to avoid underpayment on rounding
        eth_amount_wei = int((float(total_usd) / eth_price_usd) * 1e18) + 1

    options = []
    for asset in _supported_assets_for_event(provider):
        cid = asset['chainId']
        sym = asset['symbol']
        token_addr = asset['tokenAddress']
        # Skip ETH when oracle unavailable
        if sym == 'ETH' and eth_amount_wei is None:
            continue

        if sym == 'ETH':
            amount = str(eth_amount_wei)
        else:
            amount = str(usdc_amount_raw)

        balance_raw = bal_map.get((cid, sym, token_addr.lower()), '0')
        try:
            sufficient = int(balance_raw) >= int(amount)
        except (TypeError, ValueError):
            sufficient = False

        opt = {
            'asset': _build_asset_caip(cid, token_addr),
            'symbol': sym,
            'name': asset['name'],
            'chain': asset['chain'],
            'chainId': f'eip155:{cid}',
            'decimals': asset['decimals'],
            'amount': amount,
            'balance': balance_raw,
            'sufficient': sufficient,
            'expiresAt': expires_at,
        }
        if sym == 'ETH' and eth_price_usd is not None:
            opt['priceUsd'] = eth_price_usd

        # Build signingRequest only for sufficient balances
        if sufficient:
            if sym in ('USDC', 'USDT0'):
                # EIP-3009 gasless: sign TransferWithAuthorization
                from pretix_eth.x402.typed_data import build_transfer_authorization_typed_data
                from pretix_eth.x402.nonce import generate_nonce_bytes32
                auth = {
                    'from': wallet,
                    'to': recipient,
                    'value': amount,
                    'validAfter': 0,
                    'validBefore': expires_at,
                    'nonce': generate_nonce_bytes32(),
                }
                try:
                    typed = build_transfer_authorization_typed_data(
                        chain_id=cid, symbol=sym, authorization=auth,
                    )
                    opt['signingRequest'] = {
                        'method': 'eth_signTypedData_v4',
                        'params': [wallet, json.dumps(_typed_data_to_json(typed))],
                    }
                except Exception:
                    pass  # Unsupported combo — leave without signingRequest
            elif sym == 'ETH':
                opt['signingRequest'] = {
                    'method': 'eth_sendTransaction',
                    'params': [{
                        'from': wallet,
                        'to': recipient,
                        'value': '0x' + format(int(amount), 'x'),
                        'data': '0x',
                        'chainId': '0x' + format(cid, 'x'),
                    }],
                }

        options.append(opt)

    # Sort by USD balance descending so highest-value options appear first
    def _usd_value(o):
        try:
            if o['symbol'] == 'ETH' and eth_price_usd:
                return (int(o['balance']) / 1e18) * eth_price_usd
            return int(o['balance']) / (10 ** o['decimals'])
        except (TypeError, ValueError):
            return 0
    options.sort(key=_usd_value, reverse=True)

    return JsonResponse({'options': options})


# ---------------------------------------------------------------------------
# Voucher validation + discount
# ---------------------------------------------------------------------------

def validate_voucher(event, code: str) -> dict:
    """Validate a voucher code via Pretix ORM. Returns dict with
    {valid, code, priceMode, value, itemId, maxUsages, redeemed, error?}."""
    invalid = lambda err: {
        'valid': False, 'code': code, 'priceMode': 'none', 'value': '0',
        'itemId': None, 'maxUsages': 0, 'redeemed': 0, 'error': err,
    }
    try:
        from pretix.base.models import Voucher
        with scopes_disabled():
            try:
                v = Voucher.objects.get(event=event, code__iexact=code)
            except Voucher.DoesNotExist:
                return invalid('Voucher code not found')
            if v.valid_until and timezone.now() > v.valid_until:
                return invalid('Voucher has expired')
            if v.max_usages and v.redeemed >= v.max_usages:
                return invalid('Voucher has been fully redeemed')
            return {
                'valid': True,
                'code': v.code,
                'priceMode': v.price_mode or 'none',
                'value': str(v.value or '0'),
                'itemId': v.item_id,
                'maxUsages': v.max_usages or 0,
                'redeemed': v.redeemed or 0,
            }
    except Exception as e:
        return invalid(f'Failed to validate voucher: {e}')


def apply_voucher_discount(original_price: Decimal, voucher: dict) -> Decimal:
    """Compute discounted price for an item given a validated voucher.
    Matches devcon's priceMode logic: set / subtract / percent / none."""
    value = Decimal(voucher.get('value', '0'))
    mode = voucher.get('priceMode', 'none')
    if mode == 'set':
        return value.quantize(Decimal('0.01'))
    if mode == 'subtract':
        return max(Decimal('0'), original_price - value).quantize(Decimal('0.01'))
    if mode == 'percent':
        return max(Decimal('0'), original_price - (original_price * value / Decimal('100'))).quantize(Decimal('0.01'))
    return original_price


# ---------------------------------------------------------------------------
# Purchase
# ---------------------------------------------------------------------------

def get_ticket_purchase_info(event):
    """Query Pretix's Django ORM for ticket catalog info.
    Returns the shape expected by the purchase endpoint:
    {
      tickets: [{id, name, price, available, isAdmission, requireVoucher, variations}],
      event: {currency},
    }
    """
    from pretix.base.models import Item, Quota
    with scopes_disabled():
        items = Item.objects.filter(event=event, active=True).select_related('category')
        tickets = []
        for item in items:
            # Check availability via quotas
            quotas = item.quotas.all()
            available = any(q.availability()[0] == Quota.AVAILABILITY_OK for q in quotas) if quotas.exists() else True
            variations = []
            for var in item.variations.filter(active=True):
                variations.append({
                    'id': var.pk,
                    'name': str(var.value),
                    'price': str(var.default_price or item.default_price),
                })
            tickets.append({
                'id': item.pk,
                'name': str(item.name),
                'price': str(item.default_price),
                'available': available,
                'isAdmission': item.admission,
                'requireVoucher': item.require_voucher,
                'variations': variations,
            })
    return {
        'tickets': tickets,
        'event': {'currency': event.currency},
    }


@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_token
def purchase(request):
    """Create a pending x402 order. Returns HTTP 402 with payment details."""
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer
    # (see docs/superpowers/plans/2026-04-15-x402-consolidation.md Appendix A)

    provider = _get_provider(event)

    # Rate limit
    client_ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR', 'unknown')
    if not ticketstore.check_purchase_rate_limit(client_ip=client_ip):
        return JsonResponse({'success': False, 'error': 'rate limit exceeded'}, status=429)

    # Validation
    required = ('email', 'intended_payer', 'tickets')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({
            'success': False, 'error': f'missing fields: {missing}',
        }, status=400)

    # Validate voucher (optional)
    voucher_data = None
    voucher_code = body.get('voucher')
    if voucher_code:
        voucher_data = validate_voucher(event, voucher_code)
        if not voucher_data['valid']:
            return JsonResponse({
                'success': False,
                'error': voucher_data.get('error', 'Invalid voucher'),
            }, status=400)

    # Fetch ticket info + calculate total
    ticket_info = get_ticket_purchase_info(event)
    items_by_id = {t['id']: t for t in ticket_info['tickets']}
    subtotal = Decimal('0')
    voucher_discount = Decimal('0')
    order_tickets = []

    MAX_QTY_PER_LINE = 10  # matches devcon's per-item quantity cap

    def _parse_qty(raw):
        """Coerce a client-supplied quantity to a bounded int. Raises ValueError
        on non-numeric, zero/negative, or excessive values."""
        try:
            q = int(raw if raw is not None else 1)
        except (TypeError, ValueError):
            raise ValueError(f'invalid quantity: {raw!r}')
        if q < 1:
            raise ValueError(f'quantity must be >= 1 (got {q})')
        if q > MAX_QTY_PER_LINE:
            raise ValueError(f'quantity must be <= {MAX_QTY_PER_LINE} (got {q})')
        return q

    def _resolve_variation_price(item, variation_id):
        """Return (price, variation_id_or_None). If variation_id is provided,
        it MUST match an active variation for this item; otherwise raise ValueError.
        This prevents underpricing attacks via invalid variation IDs."""
        if variation_id is None or variation_id == '':
            return Decimal(item['price']), None
        try:
            vid = int(variation_id)
        except (TypeError, ValueError):
            raise ValueError(f'invalid variationId: {variation_id!r}')
        for var in item.get('variations') or []:
            if var['id'] == vid:
                return Decimal(var['price']), vid
        raise ValueError(
            f"variation {vid} is not a valid active variation for item {item['id']}"
        )

    # Tickets (with variation pricing)
    for req in body['tickets']:
        item = items_by_id.get(req['itemId'])
        if item is None or not item['available']:
            return JsonResponse({
                'success': False,
                'error': f'ticket {req["itemId"]} unavailable',
            }, status=400)
        try:
            qty = _parse_qty(req.get('quantity', 1))
            original_price, resolved_var_id = _resolve_variation_price(item, req.get('variationId'))
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        # Apply voucher discount if applicable (voucher may target a specific item)
        if voucher_data and voucher_data['valid']:
            if voucher_data['itemId'] is None or voucher_data['itemId'] == item['id']:
                price = apply_voucher_discount(original_price, voucher_data)
            else:
                price = original_price
        else:
            price = original_price
        voucher_discount += (original_price - price) * qty
        subtotal += original_price * qty
        order_tickets.append({
            'item': item, 'quantity': qty,
            'price': str(price), 'variationId': resolved_var_id,
        })

    # Addons (with variation pricing)
    order_addons = []
    for req in body.get('addons') or []:
        item = items_by_id.get(req['itemId'])
        if item is None:
            return JsonResponse({
                'success': False,
                'error': f'addon {req["itemId"]} unavailable',
            }, status=400)
        try:
            qty = _parse_qty(req.get('quantity', 1))
            addon_price, resolved_var_id = _resolve_variation_price(item, req.get('variationId'))
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        subtotal += addon_price * qty
        order_addons.append({
            'item': item, 'quantity': qty,
            'price': str(addon_price), 'variationId': resolved_var_id,
        })

    # Defense-in-depth: if tickets list is empty OR subtotal is non-positive, reject.
    # The _parse_qty check above should catch this at the per-line level, but
    # we also guard the aggregate to be safe against any future regression.
    if not order_tickets or subtotal <= Decimal('0'):
        return JsonResponse({
            'success': False,
            'error': 'order must contain at least one ticket with a positive total',
        }, status=400)

    discount_pct = Decimal(str(provider.settings.get('crypto_discount_percent', default='0')))
    crypto_discount = ((subtotal - voucher_discount) * discount_pct / Decimal('100')).quantize(Decimal('0.01'))
    total = subtotal - voucher_discount - crypto_discount

    # Build payment reference + pending order
    payment_reference = f'x402_{secrets.token_hex(16)}'
    ttl = timedelta(hours=1)

    # Pre-compute ETH amount in wei per chain (for secure native ETH verification).
    # If ETH oracle is unavailable, ETH payments won't be verifiable — stablecoins still work.
    import asyncio
    from pretix_eth.pricing import fetch_eth_price_usd
    expected_eth_wei_by_chain = {}
    try:
        eth_price_result = asyncio.run(fetch_eth_price_usd())
        if eth_price_result:
            enabled_chains = [
                cid for cid in SUPPORTED_CHAINS
                if str(provider.settings.get(f'chain_{cid}', default='True')).lower() in ('true', '1', 'yes')
            ]
            for cid in enabled_chains:
                wei = usd_to_token_raw(total, 'ETH', chain_id=cid, eth_price=eth_price_result.price)
                expected_eth_wei_by_chain[str(cid)] = str(wei)
    except Exception:
        pass  # ETH disabled; stablecoins still work

    # Build per-ticket/addon order data with resolved prices (voucher-discounted if applicable).
    # This is what gets passed to create_pretix_order at verify time to build OrderPositions.
    enriched_tickets = [
        {
            'itemId': t['item']['id'],
            'variationId': t.get('variationId'),
            'quantity': t['quantity'],
            'price': t['price'],  # already the voucher-discounted per-unit price
        }
        for t in order_tickets
    ]
    enriched_addons = [
        {
            'itemId': a['item']['id'],
            'variationId': a.get('variationId'),
            'quantity': a['quantity'],
            'price': a['price'],
        }
        for a in order_addons
    ]

    with scopes_disabled():
        ticketstore.store_pending_order(
            event=event,
            payment_reference=payment_reference,
            order_data={
                'email': body['email'],
                'tickets': enriched_tickets,
                'addons': enriched_addons,
                'answers': body.get('answers', []),
                'attendee': body.get('attendee', {}),
                'payment_provider': 'x402_crypto',
                'locale': body.get('locale', 'en'),
                **({'voucher': voucher_code} if voucher_code else {}),
            },
            total_usd=total,
            expires_at=timezone.now() + ttl,
            intended_payer=body['intended_payer'],
            expected_eth_amount_wei_by_chain=expected_eth_wei_by_chain or None,
            metadata={
                'ticketIds': [t['item']['id'] for t in order_tickets],
                'email': body['email'],
            },
        )

    # Response keys use camelCase to match the existing devcon frontend contract.
    # The frontend reads data.paymentDetails.payment.paymentReference, data.orderSummary, etc.
    recipient_addr = provider.settings.get('payment_recipient')
    return JsonResponse({
        'success': True,
        'paymentRequired': True,
        'paymentDetails': {
            'payment': {
                'paymentReference': payment_reference,
                'amount': str(usd_to_token_raw(total, 'USDC', chain_id=8453, eth_price=None)),
                'amountFormatted': f'{total} USD',
                'recipient': recipient_addr,
                'tokenAddress': '',
                'tokenSymbol': 'USDC',
                'tokenDecimals': 6,
                'network': '',
                'chainId': 0,
                'expiresAt': int((timezone.now() + ttl).timestamp()),
            },
        },
        'orderSummary': {
            'tickets': [{'name': t['item']['name'], 'price': t['price'], 'quantity': t['quantity']} for t in order_tickets],
            'addons': [{'name': a['item']['name'], 'price': a['price'], 'quantity': a['quantity']} for a in order_addons],
            'subtotal': str(subtotal),
            'voucherDiscount': str(voucher_discount),
            'cryptoDiscount': str(crypto_discount),
            'total': str(total),
            'currency': ticket_info['event']['currency'],
            **(({'voucher': voucher_code} if voucher_code else {})),
        },
    }, status=402)


# ---------------------------------------------------------------------------
# Task 23: prepare_authorization
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_token
def prepare_authorization(request):
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer
    # (see docs/superpowers/plans/2026-04-15-x402-consolidation.md Appendix A)

    required = ('payment_reference', 'from', 'chain_id', 'symbol')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({
            'success': False, 'error': f'missing fields: {missing}',
        }, status=400)

    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'invalid chain_id'}, status=400)

    if body['symbol'] not in ('USDC', 'USDT0'):
        return JsonResponse({
            'success': False, 'error': 'prepare_authorization is only for gasless stablecoins',
        }, status=400)

    with scopes_disabled():
        pending = ticketstore.get_pending_order(
            event=event, payment_reference=body['payment_reference'],
        )
    if pending is None:
        return JsonResponse({'success': False, 'error': 'payment_reference not found or expired'}, status=404)

    if not _addr_eq(pending.intended_payer, body['from']):
        return JsonResponse({
            'success': False, 'error': 'from does not match intendedPayer',
        }, status=403)

    provider = _get_provider(event)
    recipient = provider.settings.get('payment_recipient')
    if not recipient:
        return JsonResponse({'success': False, 'error': 'merchant recipient not configured'}, status=500)

    amount_raw = usd_to_token_raw(
        pending.total_usd, body['symbol'], chain_id=chain_id, eth_price=None,
    )
    authorization = {
        'from': body['from'],
        'to': recipient,
        'value': str(amount_raw),
        'validAfter': 0,
        'validBefore': int(pending.expires_at.timestamp()),
        'nonce': generate_nonce_bytes32(),
    }
    typed_data = build_transfer_authorization_typed_data(
        chain_id=chain_id, symbol=body['symbol'], authorization=authorization,
    )
    return JsonResponse({
        'success': True,
        'authorization': authorization,
        'typed_data': typed_data,
    })


# ---------------------------------------------------------------------------
# Task 24: execute_transfer
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_token
def execute_transfer(request):
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer
    # (see docs/superpowers/plans/2026-04-15-x402-consolidation.md Appendix A)

    required = ('payment_reference', 'authorization', 'chain_id', 'symbol')
    missing = [k for k in required if body.get(k) is None]
    if missing:
        return JsonResponse({
            'success': False, 'error': f'missing fields: {missing}',
        }, status=400)

    # Accept both signature formats from devcon checkout.tsx:
    # - EOA: { signature: { v: number, r: "0x...", s: "0x..." } }
    # - Smart wallet: { rawSignature: "0x..." }
    raw_sig = body.get('rawSignature')
    sig_obj = body.get('signature')
    if raw_sig and isinstance(raw_sig, str):
        signature_hex = raw_sig
    elif sig_obj and isinstance(sig_obj, dict):
        # Reassemble v/r/s into a 65-byte hex string
        try:
            r_hex = sig_obj['r'][2:] if sig_obj['r'].startswith('0x') else sig_obj['r']
            s_hex = sig_obj['s'][2:] if sig_obj['s'].startswith('0x') else sig_obj['s']
            v = int(sig_obj['v'])
            signature_hex = '0x' + r_hex + s_hex + format(v, '02x')
        except (KeyError, TypeError, ValueError) as e:
            return JsonResponse({'success': False, 'error': f'invalid signature object: {e}'}, status=400)
    elif sig_obj and isinstance(sig_obj, str):
        # Plain hex string (alternative client format)
        signature_hex = sig_obj
    else:
        return JsonResponse({
            'success': False, 'error': 'signature or rawSignature is required',
        }, status=400)

    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'invalid chain_id'}, status=400)

    with scopes_disabled():
        pending = ticketstore.get_pending_order(
            event=event, payment_reference=body['payment_reference'],
        )
    if pending is None:
        return JsonResponse({'success': False, 'error': 'payment_reference not found'}, status=404)

    auth = body['authorization']
    if not _addr_eq(pending.intended_payer, auth.get('from', '')):
        return JsonResponse({'success': False, 'error': 'authorization.from does not match intendedPayer'}, status=403)

    # Fix 5 — validate authorization fields against order terms before sponsoring gas
    provider = _get_provider(event)
    recipient = provider.settings.get('payment_recipient')
    if recipient and not _addr_eq(auth.get('to', ''), recipient):
        return JsonResponse({'success': False, 'error': 'authorization.to does not match configured recipient'}, status=400)
    expected_amount = usd_to_token_raw(pending.total_usd, body['symbol'], chain_id=chain_id, eth_price=None)
    if expected_amount <= 0:
        # Defense-in-depth: a pending order with a non-positive total is malformed
        # and should never be executable. Prevents trivially-satisfiable auth values.
        return JsonResponse({
            'success': False,
            'error': f'pending order has invalid expected amount: {expected_amount}',
        }, status=400)
    if int(auth.get('value', 0)) < expected_amount:
        return JsonResponse({
            'success': False,
            'error': f'authorization.value ({auth.get("value")}) < expected ({expected_amount})',
        }, status=400)
    now_ts = int(timezone.now().timestamp())
    if int(auth.get('validBefore', 0)) < now_ts:
        return JsonResponse({'success': False, 'error': 'authorization already expired'}, status=400)

    relayer_pk = resolve_relayer_pk(provider.settings.get('relayer_private_key', default=None))
    if not relayer_pk:
        return JsonResponse({'success': False, 'error': 'relayer not configured'}, status=503)
    alchemy_key = provider.settings.get('alchemy_api_key', default=None) or None

    try:
        result: RelayerResult = execute_transfer_with_authorization(
            chain_id=chain_id,
            symbol=body['symbol'],
            authorization=auth,
            signature=signature_hex,
            relayer_pk=relayer_pk,
            alchemy_key=alchemy_key,
        )
    except GasConditionError as e:
        # Transient: network fees above our cap. Safe to retry in a short while.
        resp = JsonResponse({
            'success': False,
            'error': str(e),
            'category': 'gas_price_too_high',
        }, status=503)
        resp['Retry-After'] = '30'
        return resp
    except RelayerInsufficientFundsError as e:
        # Non-retryable: wallet drained, operator must top up.
        return JsonResponse({
            'success': False,
            'error': str(e),
            'category': 'relayer_insufficient_funds',
        }, status=502)
    except RelayerError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=503)

    return JsonResponse({
        'success': True,
        'txHash': result.tx_hash,
        'chainId': result.chain_id,
    })


# ---------------------------------------------------------------------------
# Task 25: verify
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
@require_pretix_token
def verify(request):
    body = _read_body(request)
    event = _get_event(body.get('organizer', ''), body.get('event', ''))
    if not event:
        return JsonResponse({'success': False, 'error': 'event not found'}, status=404)
    # TODO: enforce event-level authorization — verify token.team has access to event.organizer
    # (see docs/superpowers/plans/2026-04-15-x402-consolidation.md Appendix A)

    required = ('payment_reference', 'tx_hash', 'payer', 'chain_id', 'symbol')
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({'success': False, 'error': f'missing fields: {missing}'}, status=400)

    tx_hash = body['tx_hash']
    if not _TX_HASH_RE.match(tx_hash):
        return JsonResponse({'success': False, 'error': 'invalid tx_hash format'}, status=400)

    try:
        chain_id = int(body['chain_id'])
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'invalid chain_id'}, status=400)

    # Rate limit
    client_ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR', 'unknown')
    with scopes_disabled():
        if not ticketstore.check_verify_rate_limit(
            payment_reference=body['payment_reference'], client_ip=client_ip,
        ):
            return JsonResponse({'success': False, 'error': 'rate limit exceeded'}, status=429)

        # One-time tx_hash
        if ticketstore.get_completed_by_tx_hash(tx_hash):
            return JsonResponse({'success': False, 'error': 'tx already used for a completed order'}, status=400)

        # Pending order
        pending = ticketstore.get_pending_order(event=event, payment_reference=body['payment_reference'])
        if pending is None:
            return JsonResponse({'success': False, 'error': 'payment_reference not found or expired'}, status=404)

        if not _addr_eq(pending.intended_payer, body['payer']):
            return JsonResponse({'success': False, 'error': 'payer does not match intendedPayer'}, status=403)

    provider = _get_provider(event)
    alchemy_key = provider.settings.get('alchemy_api_key', default=None) or None
    min_conf = int(provider.settings.get('min_confirmations', default=1))
    recipient = provider.settings.get('payment_recipient')

    w3 = _w3_for_chain(chain_id, alchemy_key)

    # Dispatch by symbol
    if body['symbol'] == 'ETH':
        # ETH path requires a payer signature (prevents cross-order tx reuse).
        # USDC/USDT0 are already bound via EIP-3009 and don't need this.
        eth_sig = body.get('ethPayerSignature')
        if not eth_sig:
            return JsonResponse({
                'success': False,
                'error': 'ethPayerSignature is required for native ETH payments',
            }, status=400)
        from pretix_eth.verification import build_eth_payer_message, verify_eth_payer_signature
        eth_msg = build_eth_payer_message(body['payment_reference'], body['payer'], chain_id)
        if not verify_eth_payer_signature(w3=w3, payer=body['payer'], message=eth_msg, signature=eth_sig):
            return JsonResponse({
                'success': False,
                'error': 'ethPayerSignature does not match the payer address',
            }, status=403)

        expected_wei_str = (pending.expected_eth_amount_wei_by_chain or {}).get(str(chain_id))
        if not expected_wei_str:
            return JsonResponse({'success': False, 'error': 'no ETH wei recorded for this chain'}, status=400)
        vr = verify_native_eth(
            w3=w3, tx_hash=tx_hash,
            expected_from=body['payer'], expected_to=recipient,
            expected_amount_wei=int(expected_wei_str), min_confirmations=min_conf,
        )
    else:
        contract = get_token_contract(chain_id, body['symbol'])
        if contract is None:
            return JsonResponse({'success': False, 'error': 'unsupported chain/token combo'}, status=400)
        expected_amount = usd_to_token_raw(
            pending.total_usd, body['symbol'], chain_id=chain_id, eth_price=None,
        )
        vr = verify_erc20_transfer(
            w3=w3, chain_id=chain_id, tx_hash=tx_hash,
            expected_from=body['payer'], expected_to=recipient,
            expected_token=contract['address'], expected_amount=expected_amount,
            min_confirmations=min_conf,
        )

    if not vr.verified:
        return JsonResponse({'success': False, 'error': vr.error}, status=400)

    # Record crypto amount paid (for admin reporting) + relayer-sponsored gas.
    # Only ERC-20 flows go through our relayer; native ETH payers cover their
    # own gas, so gas_cost_wei stays null there.
    crypto_amount = (
        str(expected_wei_str) if body['symbol'] == 'ETH' else str(expected_amount)
    )
    gas_cost_wei = None
    if body['symbol'] in ('USDC', 'USDT0'):
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            gas_used = int(receipt.get('gasUsed', 0) or 0)
            effective_price = int(receipt.get('effectiveGasPrice', 0) or 0)
            if gas_used and effective_price:
                gas_cost_wei = str(gas_used * effective_price)
        except Exception as e:
            log.warning('Could not fetch receipt for gas accounting (tx=%s): %s', tx_hash, e)

    # Atomic claim + reserve
    with scopes_disabled():
        claimed = ticketstore.claim_pending_order(event=event, payment_reference=body['payment_reference'])
        if claimed is None:
            return JsonResponse({'success': False, 'error': 'already claimed'}, status=409)

        try:
            ticketstore.reserve_completed_order(
                event=event, tx_hash=tx_hash,
                payment_reference=body['payment_reference'],
                payer=body['payer'], chain_id=chain_id,
                total_usd=claimed.total_usd, token_symbol=body['symbol'],
                crypto_amount=crypto_amount, gas_cost_wei=gas_cost_wei,
            )
        except ticketstore.TxHashAlreadyUsedError:
            ticketstore.store_pending_order(
                event=claimed.event, payment_reference=claimed.payment_reference,
                order_data=claimed.order_data, total_usd=claimed.total_usd,
                expires_at=claimed.expires_at, intended_payer=claimed.intended_payer,
                expected_eth_amount_wei_by_chain=claimed.expected_eth_amount_wei_by_chain,
                expected_chain_id=claimed.expected_chain_id,
                metadata=claimed.metadata,
            )
            return JsonResponse({'success': False, 'error': 'tx already used (race)'}, status=409)

        # Create Pretix order + confirm payment (Task 26)
        try:
            pretix_order = create_pretix_order(
                event=event, order_data=claimed.order_data,
                total_usd=str(claimed.total_usd),
            )
        except Exception as e:
            ticketstore.remove_completed_reservation(event=event, payment_reference=body['payment_reference'])
            ticketstore.store_pending_order(
                event=claimed.event, payment_reference=claimed.payment_reference,
                order_data=claimed.order_data, total_usd=claimed.total_usd,
                expires_at=claimed.expires_at, intended_payer=claimed.intended_payer,
                expected_eth_amount_wei_by_chain=claimed.expected_eth_amount_wei_by_chain,
                expected_chain_id=claimed.expected_chain_id,
                metadata=claimed.metadata,
            )
            return JsonResponse({'success': False, 'error': f'pretix order creation failed: {e}'}, status=500)

        confirm_x402_payment(
            order=pretix_order, tx_hash=tx_hash, payer=body['payer'],
            chain_id=chain_id, token_symbol=body['symbol'],
        )
        ticketstore.finalize_completed_order(
            event=event, payment_reference=body['payment_reference'],
            pretix_order_code=pretix_order.code,
        )

    return JsonResponse({
        'success': True,
        'order': {
            'code': pretix_order.code,
            'secret': pretix_order.secret,
        },
        'payment': {
            'txHash': body['tx_hash'],
            'payer': body['payer'],
            'blockNumber': vr.block_number or 0,
        },
    })
