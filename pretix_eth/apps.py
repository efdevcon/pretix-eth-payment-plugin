from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from . import __version__


class EthApp(AppConfig):
    name = 'pretix_eth'
    verbose_name = 'Pretix Ethereum Payment'

    class PretixPluginMeta:
        name = _('Ethereum payment')
        author = 'Ethereum Foundation'
        category = 'PAYMENT'
        description = _('Accept Ethereum-based payments (ETH, USDC, USDT0) directly in Pretix checkout.')
        visible = True
        version = __version__

    def ready(self):
        import logging
        import os
        import sys
        # Marker log line: one entry per process that booted pretix_eth.
        # Includes argv so we can tell web (gunicorn) from celery worker.
        logging.getLogger(__name__).info(
            'pretix_eth[boot]: AppConfig.ready() running pid=%s argv=%s',
            os.getpid(), ' '.join(sys.argv[:3]),
        )
        from . import signals  # noqa
        _install_order_placed_email_suppressor()
        _install_fiat_provider_restrictor()
        _install_fiat_fee_name_decoration()
        _install_fiat_per_item_markup()
        _install_stripe_mail_render()
        _install_payment_info_autofill()


def _install_order_placed_email_suppressor():
    """Monkey-patch `pretix.base.services.orders._order_placed_email` (and the
    per-attendee variant) so the "Order Placed" email is skipped for orders
    whose payment provider is `walletconnect` AND whose event has opted in via
    the provider's `suppress_order_placed_email` setting.

    Crypto checkouts typically settle in seconds, making the placed → paid
    email pair redundant. Stripe / bank-transfer orders still get the placed
    email. The patch is no-op for any other provider, so other payment plugins
    on the same Pretix instance are unaffected.

    Why monkey-patch rather than a signal: Pretix's `order_placed` signal
    fires AFTER the placed email has already been queued, and there is no
    "before email" signal that lets a plugin cancel the send. The two
    `_order_placed_email*` functions are module-level in
    `pretix.base.services.orders` and called inline from `_perform_order`, so
    re-binding them at app-ready time is the cleanest interception point.

    If Pretix renames the functions in a future version, the import fails
    cleanly here and the admin toggle becomes a no-op (we log a warning) —
    rather than crashing the worker at order-placed time.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from pretix.base.services import orders as _orders
        orig_buyer = _orders._order_placed_email
        orig_attendee = _orders._order_placed_email_attendee
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: could not install order-placed email suppressor: %s. '
            'The "Suppress Order Placed email" admin toggle will have no effect.',
            e,
        )
        return

    def _should_suppress(event, order):
        # Single-payment short-circuit: walletconnect orders have exactly one
        # OrderPayment row at placement time. Stripe also settles within
        # seconds (card capture, gpay, etc.) so the placed+paid email pair
        # is redundant for those too — gate via the same toggle.
        try:
            payment = order.payments.first()
        except Exception:
            return False
        if not payment:
            return False
        provider = (getattr(payment, 'provider', '') or '')
        is_fast_settling = (
            provider == 'walletconnect'
            or provider.startswith('stripe')  # stripe_cc, stripe_sepa_debit, etc.
        )
        if not is_fast_settling:
            return False
        return bool(event.settings.get(
            'payment_walletconnect_suppress_order_placed_email',
            as_type=bool,
            default=False,
        ))

    def _wrapped_buyer(event, order, *args, **kwargs):
        if _should_suppress(event, order):
            log.info(
                'pretix_eth: skipping Order Placed email for order %s (provider=walletconnect, '
                'suppress_order_placed_email=True)',
                order.code,
            )
            return
        return orig_buyer(event, order, *args, **kwargs)

    def _wrapped_attendee(event, order, *args, **kwargs):
        if _should_suppress(event, order):
            return
        return orig_attendee(event, order, *args, **kwargs)

    _orders._order_placed_email = _wrapped_buyer
    _orders._order_placed_email_attendee = _wrapped_attendee


def _install_fiat_provider_restrictor():
    """Monkey-patch `pretix.base.payment.BasePaymentProvider.is_allowed`
    so that EVERY non-crypto (fiat) payment method — Stripe card/SEPA, PayPal,
    bank transfer, gift card, offline, any other card plugin — is hidden
    whenever the current cart or order contains an item whose
    `meta_data.fiat_disabled` is truthy. The crypto rail (`walletconnect`) is
    exempt via `_is_crypto_provider_ident`.

    V73: this used to patch only `StripeMethod`, so any other fiat rail an
    operator enabled would still let a buyer pay a fiat_disabled (crypto-only)
    item. Patching the base class covers all current and future non-crypto
    rails; concrete providers that override is_allowed all call
    `super().is_allowed()`, so the base hook still fires for them.

    Storage model: each `Item` carries its own `fiat_disabled` value via
    Pretix's `ItemMetaProperty` / `ItemMetaValue` (set in the standard
    Items > Edit > Metadata tab, or via the API). A truthy value
    ("true", "yes", "1") on any base position in the cart hides fiat rails.

    Why monkey-patch: Pretix has no first-class "this item bans this
    payment method" config. Overriding `is_allowed` covers BOTH checkout
    flows (cart → pay, and order → change payment method) with one
    server-side hook that can't be bypassed by hand-crafting a URL.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from pretix.base.payment import BasePaymentProvider
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: BasePaymentProvider not importable (%s); '
            'per-item fiat_disabled blocking will have no effect.',
            e,
        )
        return

    orig_is_allowed = BasePaymentProvider.is_allowed
    if getattr(orig_is_allowed, '_ped_fiat_wrapped', False):
        return  # idempotent: already patched (worker reload)

    def _is_truthy(v):
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ('true', 'yes', '1')

    def _is_blocked_for_fiat(provider, request):
        event = provider.event
        from pretix.base.models import CartPosition, Item, OrderPosition

        def _any_item_fiat_disabled(item_ids):
            if not item_ids:
                return None  # no items checked
            # Item.meta_data aggregates ItemMetaValue rows on access. One
            # query for the items, then in-memory iteration; small N
            # (cart size is tiny) so this is fine.
            items = Item.objects.filter(pk__in=set(item_ids))
            for it in items:
                if _is_truthy((it.meta_data or {}).get('fiat_disabled')):
                    log.info(
                        'pretix_eth: fiat blocked event=%s item=%s (meta_data.fiat_disabled truthy)',
                        event.slug, it.pk,
                    )
                    return it.pk
            return None

        # Cart flow — buyer is in checkout, no order yet.
        cart_id = None
        try:
            from pretix.presale.views.cart import get_or_create_cart_id
            cart_id = get_or_create_cart_id(request, create=False)
        except Exception as e:
            log.debug('pretix_eth: get_or_create_cart_id failed (%s); falling back to session key', e)
        if not cart_id:
            try:
                cart_id = request.session.get('current_cart_event_{}'.format(event.pk))
            except Exception:
                cart_id = None

        # Only main positions dictate payment-method visibility. Add-ons
        # follow their parent's payment treatment, so a fiat_disabled add-on
        # under a fiat-allowed main item should not hide Stripe.
        if cart_id:
            cart_item_ids = list(CartPosition.objects.filter(
                cart_id=cart_id, event=event, addon_to__isnull=True,
            ).values_list('item_id', flat=True))
            if _any_item_fiat_disabled(cart_item_ids):
                return True

        # Order re-pay flow — order code lives in the URL kwargs.
        try:
            match = getattr(request, 'resolver_match', None)
            order_code = match.kwargs.get('order') if match else None
        except Exception:
            order_code = None
        if order_code:
            order_item_ids = list(OrderPosition.objects.filter(
                order__code=order_code, order__event=event, addon_to__isnull=True,
            ).values_list('item_id', flat=True))
            if _any_item_fiat_disabled(order_item_ids):
                return True

        return False

    def _wrapped_is_allowed(self, request, total=None):
        # Crypto rail (walletconnect) is never restricted by fiat_disabled.
        if _is_crypto_provider_ident(getattr(self, 'identifier', '')):
            return orig_is_allowed(self, request, total)
        if _is_blocked_for_fiat(self, request):
            return False
        return orig_is_allowed(self, request, total)

    _wrapped_is_allowed._ped_fiat_wrapped = True
    BasePaymentProvider.is_allowed = _wrapped_is_allowed


def _current_cart_markup_sum(event):
    """Compute the per-item Stripe markup for the buyer's current cart
    on `event`, in event currency, as a Decimal.

    Each cart position contributes `max(0, fiat_price_usd - position.price)`
    when its item carries a `fiat_price_usd` ItemMetaValue, and contributes
    `0` otherwise. Add-ons contribute on their own metadata, same rule.

    Reads positions from the thread-local that `_install_fiat_per_item_markup`
    populates (covers both presale requests AND order placement in Celery).
    Returns `Decimal('0')` when no context is available so the public-name
    decoration falls back to the un-prefixed label rather than guessing.

    Used by:
      - `_install_fiat_per_item_markup` to override Stripe's calculate_fee
      - `_install_fiat_fee_name_decoration` to suppress / format the
        chooser-label prefix
    """
    from decimal import Decimal
    ctx = globals().get('_fee_exempt_ctx')
    if ctx is None:
        return Decimal('0')
    positions = getattr(ctx, 'positions', None)
    if positions is not None:
        return _markup_sum_from_positions(positions)
    request = getattr(ctx, 'request', None)
    if request is None:
        return Decimal('0')

    # Order re-pay flow (buyer changing payment method on an existing order):
    # resolve markup from the order's positions before the cart fallback.
    order_markup = _markup_sum_from_order_request(request, event)
    if order_markup is not None:
        return order_markup

    # Fall back to a cart_id lookup from the request session.
    cart_id = None
    try:
        from pretix.presale.views.cart import get_or_create_cart_id
        cart_id = get_or_create_cart_id(request, create=False)
    except Exception:
        pass
    if not cart_id:
        try:
            cart_id = request.session.get('current_cart_event_{}'.format(event.pk))
        except Exception:
            return Decimal('0')
    if not cart_id:
        return Decimal('0')

    from pretix.base.models import CartPosition
    positions = list(CartPosition.objects.filter(
        cart_id=cart_id, event=event,
    ).select_related('item'))
    return _markup_sum_from_positions(positions)


# ---------------------------------------------------------------------------
# Fiat / crypto provider classification (V73) + metadata parsing (V81/V69/V82).
# Shared by the chooser restrictor, the calculate_fee preview, the re-pay flow,
# and the placement bake so all four paths agree on which rails are fiat and how
# each position's card price / tax is computed.
# ---------------------------------------------------------------------------

# The plugin's own crypto rails. Every OTHER payment provider is a fiat rail
# that must charge the card price (fiat_price_usd) and honor fiat_disabled.
CRYPTO_PROVIDER_IDENTIFIERS = ('walletconnect',)


def _is_crypto_provider_ident(ident):
    """True if `ident` is one of the plugin's crypto payment rails."""
    ident = ident or ''
    return any(ident == c or ident.startswith(c) for c in CRYPTO_PROVIDER_IDENTIFIERS)


def _is_fiat_payment(payment_requests, payment_provider):
    """True when ANY selected rail is non-crypto, i.e. needs the card markup +
    bake. Replaces the old Stripe-only detection (V73): a fiat rail is simply
    'not the walletconnect/crypto rail', so bank transfer, PayPal, offline, gift
    card, or any other card plugin are all covered, not just Stripe."""
    for p in payment_requests or []:
        if not _is_crypto_provider_ident(p.get('provider')):
            return True
    if payment_provider is not None:
        if not _is_crypto_provider_ident(getattr(payment_provider, 'identifier', '')):
            return True
    return False


def _parse_fiat(fiat_str):
    """Parse an operator-supplied `fiat_price_usd` metadata string into a finite,
    positive Decimal, or return None to skip the line (V81). Rejects the
    footguns: NaN and Infinity (both are 'valid' Decimals that later raise in a
    comparison — a 500 order-creation DoS — or persist a non-finite price),
    values <= 0, and the underscore form '1_000' (Python's Decimal silently
    reads it as 1000, a 1000x overcharge). Only a plain [0-9.] shape is accepted,
    which also rejects '1,000', signs, and whitespace-embedded values."""
    from decimal import Decimal, InvalidOperation
    s = (fiat_str or '').strip()
    if not s or any(c not in '0123456789.' for c in s):
        return None
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not d.is_finite() or d <= 0:
        return None
    return d


def _fiat_meta_str(p):
    """`fiat_price_usd` for a position, reading VARIATION-level metadata first and
    falling back to the item level (V69). Pretix ItemVariation.meta_data
    aggregates the variation's own metadata rows; without the variation read a
    single item-level price applied to every variation, letting the expensive
    variation dodge the card markup."""
    variation = getattr(p, 'variation', None)
    if variation is not None:
        vmeta = getattr(variation, 'meta_data', None) or {}
        v = (vmeta.get('fiat_price_usd') or '').strip()
        if v:
            return v
    item = getattr(p, 'item', None)
    imeta = (getattr(item, 'meta_data', None) or {}) if item is not None else {}
    return (imeta.get('fiat_price_usd') or '').strip()


def _gross_and_tax_for(fiat, tax_rate, tax_rule):
    """Return (price, tax_value) for a baked card price, branching on the tax
    rule's direction (V82) instead of always assuming gross-inclusive:
      - price_includes_tax (default, matches Pretix core when no rule is set):
        fiat is GROSS -> price = fiat, tax = fiat*rate/(100+rate).
      - not price_includes_tax: fiat is NET -> tax = fiat*rate/100,
        price = fiat + tax.
    tax_value is quantized to cents (ROUND_HALF_UP). Tax-exempt (rate 0/None)
    yields tax 0 and price = fiat."""
    from decimal import Decimal, ROUND_HALF_UP
    cents = Decimal('0.01')
    if not tax_rate or tax_rate <= 0:
        return fiat, Decimal('0')
    includes = getattr(tax_rule, 'price_includes_tax', True)
    if includes:
        price = fiat
        tax_value = (fiat * tax_rate / (Decimal('100') + tax_rate)).quantize(
            cents, rounding=ROUND_HALF_UP)
    else:
        tax_value = (fiat * tax_rate / Decimal('100')).quantize(
            cents, rounding=ROUND_HALF_UP)
        price = fiat + tax_value
    return price, tax_value


def _list_price(p):
    """Pre-voucher / pre-discount listed price of a position — the denominator
    for the discount ratio. Prefers Pretix's `listed_price` (the catalog price
    before any voucher; `price_after_voucher`/`price` is what's left after),
    falling back to the variation or item default price for older rows that
    predate `listed_price`. Returns a positive Decimal, or None if none is
    resolvable.
    """
    from decimal import Decimal, InvalidOperation
    for val in (
        getattr(p, 'listed_price', None),
        getattr(getattr(p, 'variation', None), 'price', None),
        getattr(getattr(p, 'item', None), 'default_price', None),
    ):
        if val is None:
            continue
        try:
            d = val if isinstance(val, Decimal) else Decimal(str(val))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if d > 0:
            return d
    return None


def _effective_fiat(p, fiat):
    """The fiat (card) price for a position after mirroring whatever discount
    Pretix applied to its crypto price, so vouchers come off BOTH prices.

    `fiat_price_usd` is the LIST fiat price (no discount). Behaviour depends on
    the position's voucher price mode (Pretix Voucher.PRICE_MODES):

      - 'set'      → set the card price to the SAME flat value V as crypto, so
                     the deal is a single price with no card premium
                     (fiat' = V).
      - 'subtract' → take the SAME absolute value V off the card price as off
                     crypto (fiat' = fiat - V), preserving the original premium.
      - 'percent' / 'none' / no voucher → scale the fiat price by the ratio the
                     crypto price moved by (fiat' = fiat * price_after_voucher /
                     listed_price). For 'percent' this is exactly the same
                     percentage; for 'none' the ratio is 1.

    The mode is read per-position, so a voucher scoped to only the ticket
    leaves add-ons at full fiat automatically. Returns the full `fiat` when no
    discount is detectable. Result is clamped at 0 and quantized to cents
    (ROUND_HALF_UP).

    IMPORTANT: the proportional branch keys off `price_after_voucher`, NOT
    `p.price`. The placement bake overwrites `p.price` with the (discounted)
    fiat value, so a ratio derived from `p.price` would read as "no discount"
    on the post-bake re-run of calculate_fee and re-add a spurious markup —
    causing an "order total has changed" mismatch. `price_after_voucher` and
    `listed_price` are stable across the bake (and copied onto OrderPositions),
    so the effective fiat stays consistent before and after baking, making the
    post-bake markup resolve to 0. Likewise 'set'/'subtract' key off the
    voucher value, not `p.price`, so they're bake-stable too.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    cents = Decimal('0.01')

    def q(v):
        return max(Decimal('0'), v).quantize(cents, rounding=ROUND_HALF_UP)

    # V63 residual: a $0 position (comp / 100%-off FREEPASS / sponsor comp, from
    # a voucher OR any other Pretix mechanism) must stay free on the card lane
    # too. Without this, a comp with no voucher object (or an admin price
    # override) would fall through to the proportional branch, find no discount
    # ratio, and re-bake the full fiat price — silently charging a card buyer for
    # a comped ticket.
    cur = getattr(p, 'price_after_voucher', None)
    if cur is None:
        cur = getattr(p, 'price', None)
    try:
        if cur is not None:
            cur_d = cur if isinstance(cur, Decimal) else Decimal(str(cur))
            if cur_d <= 0:
                return q(Decimal('0'))
    except (InvalidOperation, ValueError, TypeError):
        pass

    voucher = getattr(p, 'voucher', None)
    if voucher is not None:
        mode = getattr(voucher, 'price_mode', None)
        raw = getattr(voucher, 'value', None)
        if mode in ('set', 'subtract') and raw is not None:
            try:
                value = raw if isinstance(raw, Decimal) else Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                value = None
            if value is not None:
                if mode == 'set':
                    return q(value)          # flat deal: card = crypto = V
                return q(fiat - value)       # subtract: same V off both

    # percent / none / no voucher → proportional, keyed off the STABLE
    # price_after_voucher (see the docstring note on why not p.price).
    pav = getattr(p, 'price_after_voucher', None)
    if pav is None:
        pav = getattr(p, 'price', None)
    try:
        base = pav if isinstance(pav, Decimal) else Decimal(str(pav))
    except (InvalidOperation, ValueError, TypeError):
        return q(fiat)
    list_price = _list_price(p)
    if list_price is not None and list_price > 0 and base < list_price:
        fiat = fiat * base / list_price
    return q(fiat)


def _markup_sum_from_positions(positions):
    """Sum of per-item fiat markups (`fiat_price_usd - position.price`,
    clamped at 0) over an iterable of CartPosition or OrderPosition rows.

    Items without `fiat_price_usd` metadata contribute 0 (fiat allowed at
    `default_price`, no markup). Items with `fiat_disabled` contribute 0
    here too — the chooser-side restrictor (`_install_fiat_provider_restrictor`)
    is what actually hides Stripe, so the markup math doesn't need to
    duplicate the check.

    Add-ons contribute on their OWN metadata, not the parent's — gives
    operators independent control of add-on fiat pricing.

    Bundled children (V69) are skipped: a Pretix item-bundle child is priced at
    the bundle-internal designated_price (often $0, "included"), so marking it up
    to its standalone fiat price would charge a card buyer for an item a crypto
    buyer gets free. Per-variation metadata is read first via _fiat_meta_str.
    """
    from decimal import Decimal, InvalidOperation
    total = Decimal('0')
    for p in positions:
        if getattr(p, 'is_bundled', False):
            continue
        item = getattr(p, 'item', None)
        if item is None:
            continue
        fiat = _parse_fiat(_fiat_meta_str(p))
        if fiat is None:
            continue
        try:
            price = p.price if isinstance(p.price, Decimal) else Decimal(str(p.price))
        except (InvalidOperation, ValueError, TypeError):
            continue
        # Discount the fiat price by the same ratio Pretix applied to the
        # crypto price (voucher etc.), so the markup shrinks accordingly and
        # the card buyer gets the discount too. See _effective_fiat.
        delta = _effective_fiat(p, fiat) - price
        if delta > 0:
            total += delta
    return total


def _markup_sum_from_order_request(request, event):
    """Markup for the 'change payment method' / re-pay flow, where the buyer
    is paying an EXISTING order — there is no cart and no `_create_order`
    placement, so the order code lives in the request's `resolver_match`
    kwargs. Mirrors the order branch in `_install_fiat_provider_restrictor`.

    Returns the summed markup (Decimal) when the request targets an order, or
    None when there's no order in the URL so callers fall through to the cart
    lookup. Without this branch the markup resolves to 0 on the order-pay
    page, letting a buyer who created a crypto order switch it to Card and pay
    the (lower) ETH-denominated price — security audit HIGH finding.
    """
    try:
        match = getattr(request, 'resolver_match', None)
        order_code = match.kwargs.get('order') if match else None
    except Exception:
        order_code = None
    if not order_code:
        return None
    try:
        from pretix.base.models import OrderPosition
        # No addon filter: add-ons contribute markup on their OWN metadata,
        # matching the cart path and `_markup_sum_from_positions`. The default
        # manager excludes canceled positions (same as the restrictor).
        positions = list(OrderPosition.objects.filter(
            order__code=order_code, order__event=event,
        ).select_related('item'))
    except Exception:
        return None
    return _markup_sum_from_positions(positions)


def _install_fiat_fee_name_decoration():
    """Prefix the buyer-facing Stripe payment-method label with the
    actual markup the current cart will pay, so the chooser shows
    e.g. "+$500 · Credit Card" before the buyer commits to fiat.

    The markup is computed live from per-item metadata (the same source
    `_install_fiat_per_item_markup` uses for `calculate_fee`), so the
    chooser label and the actual fee always agree.

    No prefix is shown when the markup is 0 — i.e. all cart items have
    no `fiat_price_usd` override or their override matches their cart
    price. This handles "fiat = crypto" items cleanly without operator
    configuration.

    Patches the base `StripeMethod` plus every loaded subclass, since
    Pretix-Stripe per-method classes (card, SEPA, iDEAL, …) may define
    their own `public_name`. Fails closed on import errors — original
    labels remain unchanged.
    """
    import inspect
    import logging
    from decimal import Decimal
    log = logging.getLogger(__name__)
    try:
        from pretix.plugins.stripe.payment import StripeMethod
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: Stripe payment plugin not importable (%s); '
            'fiat-fee label decoration disabled.',
            e,
        )
        return

    def _format_money(amount, currency):
        # Strip trailing zeros so 500.00 displays as 500, 12.50 stays 12.50.
        if amount == amount.to_integral():
            num = format(amount.normalize(), 'f')
        else:
            num = format(amount, 'f').rstrip('0').rstrip('.')
        # Lead with $ for USD so the most common case stays compact; fall
        # back to "<amount> <currency-code>" for non-USD events.
        if currency == 'USD':
            return f'${num}'
        return f'{num} {currency}'.strip()

    def _make_decorated(original_getter):
        def _decorated(self):
            try:
                base = original_getter(self)
            except Exception:
                base = str(self.verbose_name)
            try:
                markup = _current_cart_markup_sum(self.event)
            except Exception:
                return base
            if markup is None or markup <= Decimal('0'):
                return base
            currency = (getattr(self.event, 'currency', '') or 'USD').strip() or 'USD'
            label = _format_money(markup, currency)
            # Front-place the markup so Stripe's auto-appended wallet list
            # ("…, Google Pay") doesn't end up after our suffix.
            return f'+{label} · {base}'
        return _decorated

    def _patch_class(cls):
        own = cls.__dict__.get('public_name')
        if isinstance(own, property) and own.fget:
            getter = own.fget
        else:
            inherited = inspect.getattr_static(cls, 'public_name', None)
            getter = inherited.fget if isinstance(inherited, property) and inherited.fget else (lambda self: str(self.verbose_name))
        cls.public_name = property(_make_decorated(getter))

    targets = [StripeMethod] + list(StripeMethod.__subclasses__())
    for cls in targets:
        try:
            _patch_class(cls)
        except Exception as e:
            log.warning('pretix_eth: failed to decorate %s.public_name: %s', cls.__name__, e)


def _install_fiat_per_item_markup():
    """Override Stripe's additional fee with a sum of per-item markups.

    Storage model: each Item carries an optional `fiat_price_usd`
    ItemMetaValue. When set and different from the position's price,
    the difference (`fiat_price_usd - price`, clamped at 0) is the
    item's contribution to the Stripe markup. When unset, the item
    contributes nothing — fiat buyers pay `default_price` with no
    markup. Companion key `fiat_disabled` is handled by the chooser
    restrictor; the markup math here just contributes 0 for those
    items (since Stripe is hidden anyway).

    Why monkey-patch: Pretix's `BasePaymentProvider.calculate_fee(price)`
    only sees a scalar — no cart breakdown — and Pretix fans the fee
    calculation across at least four code paths (cart preview,
    PaymentStep.provider_forms chooser, CartMixin.current_selected_payments,
    order placement) that don't share a clean hook. We capture the
    current presale request via Pretix's `process_request` /
    `process_response` signals into a thread-local, AND the positions
    list passed into `_create_order` / `_apply_rounding_and_fees`.
    The patched `StripeMethod.calculate_fee` reads from whichever is
    populated.

    Order-placement under Celery has no live HTTP request but always
    passes positions to `_create_order`, so the thread-local pickup
    works there too.

    Stripe-only: hooks `StripeMethod` (subclasses inherit the patched
    method). Other fiat providers keep their original fees.
    """
    import logging
    import threading
    from decimal import Decimal, InvalidOperation
    log = logging.getLogger(__name__)
    try:
        from pretix.base.payment import BasePaymentProvider
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: BasePaymentProvider not importable (%s); '
            'per-item fiat markup disabled.',
            e,
        )
        return

    # Thread-local stash for the active presale request and the positions
    # list passed into order placement. Populated by the process_request
    # receiver and the order-services wraps below; consumed by the
    # patched calculate_fee.
    ctx = threading.local()

    def _markup_for(event):
        """Resolve the markup for the cart currently in flight. Prefers
        positions stashed by `_create_order` / `_apply_rounding_and_fees`
        (covers Celery), falls back to a request → cart_id → CartPosition
        lookup.
        """
        positions = getattr(ctx, 'positions', None)
        if positions is not None:
            total = _markup_sum_from_positions(positions)
            log.info(
                'pretix_eth[markup]: from-positions count=%s total=%s',
                len(positions), total,
            )
            return total

        request = getattr(ctx, 'request', None)
        if request is None:
            log.warning('pretix_eth[markup]: no request and no positions in thread-local')
            return Decimal('0')

        # Order re-pay flow (change payment method on an existing order): the
        # markup must come from the order's positions since there's no cart
        # and no _create_order bake. Without this, switching an existing
        # crypto order to Card pays the base ETH price.
        order_markup = _markup_sum_from_order_request(request, event)
        if order_markup is not None:
            log.info('pretix_eth[markup]: from-order total=%s', order_markup)
            return order_markup

        cart_id = None
        try:
            from pretix.presale.views.cart import get_or_create_cart_id
            cart_id = get_or_create_cart_id(request, create=False)
        except Exception as e:
            log.info('pretix_eth[markup]: get_or_create_cart_id failed (%s)', e)
        if not cart_id:
            try:
                cart_id = request.session.get('current_cart_event_{}'.format(event.pk))
            except Exception as e:
                log.info('pretix_eth[markup]: session lookup failed (%s)', e)
                cart_id = None
        if not cart_id:
            log.info('pretix_eth[markup]: no cart_id resolved for event=%s', getattr(event, 'slug', '?'))
            return Decimal('0')

        from pretix.base.models import CartPosition
        positions = list(CartPosition.objects.filter(
            cart_id=cart_id, event=event,
        ).select_related('item'))
        total = _markup_sum_from_positions(positions)
        log.info(
            'pretix_eth[markup]: cart=%s positions=%s total=%s',
            cart_id, len(positions), total,
        )
        return total

    def _make_wrapped_calc(orig):
        def _wrapped(self, price):
            cls_name = type(self).__name__
            # V73: crypto rail (walletconnect) keeps its native fee — no markup.
            if _is_crypto_provider_ident(getattr(self, 'identifier', '')):
                return orig(self, price)
            log.debug('pretix_eth[calc]: %s.calculate_fee(price=%s) called pid=%s',
                      cls_name, price, _os.getpid())
            try:
                markup = _markup_for(self.event)
            except Exception as e:
                log.warning('pretix_eth[calc]: markup calc failed: %s; falling back to original fee', e)
                return orig(self, price)
            # Only override when there IS a dual-pricing markup. For carts with
            # no fiat_price_usd items (including other events on this instance)
            # the provider keeps its own configured fee — patching the BASE class
            # must not wipe legitimately-configured payment fees.
            if markup and markup > 0:
                log.debug('pretix_eth[calc]: %s markup=%s (original fee bypassed)', cls_name, markup)
                return markup
            return orig(self, price)
        return _wrapped

    # NOTE: the `calculate_fee` monkey-patch is deliberately installed LAST,
    # only after the presale request-capture signals are connected (see the
    # end of this function). Patching it here — before the signal wiring —
    # created a fail-open window: if the presale-signals import ever broke
    # (e.g. a Pretix rename), `calculate_fee` was left patched but blind
    # (no request/cart context), silently resolving every markup to $0. By
    # ordering the patch after the `.connect()` calls, a signal-wiring
    # failure returns early WITHOUT patching `calculate_fee`, so Stripe
    # keeps its native fee behaviour rather than under-charging. New-order
    # placement stays correct regardless via the `_create_order` price-bake
    # wrapped just below (which doesn't depend on the signals).
    orig_calc = BasePaymentProvider.calculate_fee

    # Wrap the function Pretix uses to compute fees during order placement.
    # The exact name varies across Pretix versions:
    #   - newer: `_apply_rounding_and_fees`
    #   - older: `_get_fees`
    # Whichever exists, wrap it so it stashes `positions` into a thread-local
    # for calculate_fee. Without this, the Celery-driven order placement
    # has no cart context and applies the full markup → mismatch with the
    # preview total → "order total has changed" error.
    import os as _os
    try:
        from pretix.base.services import orders as orders_svc
        # Diagnostic: list any fee/rounding callables so we can see what's
        # actually available in this Pretix version.
        candidates = sorted(
            n for n in dir(orders_svc)
            if ('fee' in n.lower() or 'rounding' in n.lower()) and callable(getattr(orders_svc, n, None))
        )
        log.info('pretix_eth[install]: orders module fee-candidates: %s', candidates)
    except ImportError:
        orders_svc = None
        candidates = []

    def _make_apply_wrap(name, original):
        def _wrapped(*args, **kwargs):
            positions = kwargs.get('positions')
            if positions is None and args:
                positions = args[0]
            log.info(
                'pretix_eth[apply]: %s wrap fired with %d positions (pid=%s)',
                name, len(positions or []), _os.getpid(),
            )
            prev = getattr(ctx, 'positions', None)
            ctx.positions = positions
            try:
                return original(*args, **kwargs)
            finally:
                ctx.positions = prev
        return _wrapped

    wrapped_any = False
    if orders_svc is not None:
        for cand in ('_apply_rounding_and_fees', '_get_fees', '_apply_fees_and_rounding'):
            original = getattr(orders_svc, cand, None)
            if callable(original):
                setattr(orders_svc, cand, _make_apply_wrap(cand, original))
                log.info(
                    'pretix_eth[install]: wrapped orders.%s (pid=%s)',
                    cand, _os.getpid(),
                )
                wrapped_any = True

        # Also wrap _create_order. This is the canonical entry point for
        # order placement (called both inline and from the Celery
        # perform_order task) and has remained stable across recent
        # Pretix versions. Its signature is
        # `_create_order(event, *, email, positions, now_dt, payment_requests, ...)`,
        # so positions and payment_requests are always keyword arguments.
        #
        # Two jobs at this point:
        #   1) Set the thread-local positions context for the entire duration
        #      of order creation, so calculate_fee inside
        #      `_apply_rounding_and_fees` can find them.
        #   2) For Stripe orders, choose ONE of two representations for the
        #      fiat price, gated on the event's tax-rounding mode (_bake_is_safe):
        #        - per-line rounding  → BAKE: swap each position to its fiat
        #          price so the order/invoice shows the full fiat gross ($999)
        #          with no separate fee line (markup sum becomes 0).
        #        - any sum_by_net* mode → FEE: leave positions at the crypto
        #          price and let calculate_fee add the fiat delta as a payment
        #          fee ($499 ticket + $500 fee).
        #      Why gated: the bake makes the order's tax base $999 while the
        #      checkout preview always uses $499 + $500 fee. Those two round to
        #      the same total ONLY under 'line' rounding. Under the net-total
        #      modes, a mixed-rate cart (18% ticket + 5% add-on) rounds them a
        #      cent apart, tripping Pretix's "order total has changed" guard at
        #      placement — the fee representation is consistent under every
        #      mode, so it's the safe fallback.
        def _bake_fiat_into_positions(positions):
            """In-place mutation: for each position whose item/variation carries a
            `fiat_price_usd` metadata override greater than its current price,
            swap `price` to the fiat amount and recompute `tax_value` per the
            position's tax-rule direction (V82).

            Mutates the CartPosition Python objects only. They have not
            yet been persisted as OrderPositions at this point —
            `_create_order` copies `price` and `tax_value` into the
            OrderPosition rows it creates, so the new values land
            directly in the DB without us touching the CartPosition
            table.

            Skipped for:
              - `free_price` items (buyer chose their own price)
              - `is_bundled` children (V69 — priced at the bundle-internal
                designated_price; marking them up would charge a card buyer for
                an included item a crypto buyer gets free)
            Reads variation-level metadata first (V69) and validates the metadata
            value (V81). The fiat is discounted by the same ratio Pretix applied
            to the crypto price so vouchers/comps come off the card lane too
            (V63, see _effective_fiat).
            """
            for p in positions or []:
                if getattr(p, 'is_bundled', False):
                    continue
                item = getattr(p, 'item', None)
                if item is None:
                    continue
                if getattr(item, 'free_price', False):
                    continue  # buyer-chosen price wins; don't override
                fiat = _parse_fiat(_fiat_meta_str(p))
                if fiat is None:
                    continue
                try:
                    current = p.price if isinstance(p.price, Decimal) else Decimal(str(p.price))
                except (InvalidOperation, ValueError, TypeError):
                    continue
                fiat = _effective_fiat(p, fiat)
                # _effective_fiat clamps/quantizes to a finite non-negative cents
                # value, so the compare below can't raise on NaN/Infinity (V81).
                if fiat <= current:
                    continue
                # Apply fiat price + tax, branching on the tax-rule direction
                # (V82). tax_rate is in percent (e.g. Decimal('18.00') for 18%).
                tax_rate = getattr(p, 'tax_rate', None)
                tax_rule = getattr(p, 'tax_rule', None)
                try:
                    new_price, new_tax = _gross_and_tax_for(fiat, tax_rate, tax_rule)
                    p.price = new_price
                    p.tax_value = new_tax
                except (InvalidOperation, ValueError, TypeError):
                    p.price = fiat  # keep the price bake even if tax recompute fails
                log.debug(
                    'pretix_eth[bake]: position item=%s price %s -> %s tax_value -> %s (rate=%s)',
                    getattr(item, 'pk', '?'), current, getattr(p, 'price', None),
                    getattr(p, 'tax_value', None), tax_rate,
                )

        def _bake_is_safe(event):
            """Return True only when baking the fiat price into positions is
            guaranteed to produce the same order total as the fee-based
            checkout preview — i.e. when the event uses Pretix's per-line tax
            rounding (`tax_rounding == 'line'`, the Pretix default).

            The bake represents a card ticket as its full fiat gross ($999,
            no fee line); the preview represents it as the crypto gross plus a
            payment fee ($499 + $500). Those two representations only round to
            the same total under 'line' rounding. Every `sum_by_net*` mode
            fixes each tax-rate GROUP's net and redistributes the rounding
            residual across the group's lines, so on a mixed-rate cart the
            two representations round a cent apart and Pretix rejects the
            order at placement with "the order total has changed".

            Fails safe: any non-'line' mode — or an unreadable setting — returns
            False, so we fall back to the fee representation, which is
            consistent under every rounding mode. (Setting key + values from
            pretix.base.settings.ROUNDING_MODES: 'line', 'sum_by_net',
            'sum_by_net_only_business', 'sum_by_net_keep_gross'.)
            """
            try:
                return event.settings.get('tax_rounding', default='line') == 'line'
            except Exception as e:
                log.warning('pretix_eth[create]: could not read tax_rounding (%s); skipping bake', e)
                return False

        orig_create = getattr(orders_svc, '_create_order', None)
        if callable(orig_create):
            def _wrapped_create_order(*args, **kwargs):
                positions = kwargs.get('positions')
                payment_requests = kwargs.get('payment_requests') or []
                payment_provider = kwargs.get('payment_provider')  # legacy
                log.info(
                    'pretix_eth[create]: _create_order wrap fired positions=%d payment_requests=%d '
                    'payment_provider=%s (pid=%s)',
                    len(positions or []), len(payment_requests),
                    getattr(payment_provider, 'identifier', None),
                    _os.getpid(),
                )
                if _is_fiat_payment(payment_requests, payment_provider):
                    event = kwargs.get('event') or (args[0] if args else None)
                    if event is not None and _bake_is_safe(event):
                        # Bake representation: swap each position to its fiat
                        # price so the order/invoice shows the full fiat gross
                        # ($999) with no separate fee line. Safe only under
                        # per-line tax rounding (see _bake_is_safe).
                        log.info('pretix_eth[create]: fiat payment + per-line rounding — baking fiat prices')
                        _bake_fiat_into_positions(positions)
                    else:
                        # Fee representation (no bake): leave positions at their
                        # crypto price so the inner calculate_fee adds the fiat
                        # delta as a payment fee. Consistent with the preview
                        # total under every tax-rounding mode, so it can't trip
                        # the "order total has changed" guard.
                        log.info('pretix_eth[create]: fiat payment, non-per-line rounding — using fee representation (no bake)')
                prev = getattr(ctx, 'positions', None)
                ctx.positions = positions
                try:
                    return orig_create(*args, **kwargs)
                finally:
                    ctx.positions = prev
            orders_svc._create_order = _wrapped_create_order
            log.info('pretix_eth[install]: wrapped orders._create_order (pid=%s)', _os.getpid())
            wrapped_any = True

    if not wrapped_any:
        log.warning(
            'pretix_eth[install]: no known order-side function found '
            '(tried _apply_rounding_and_fees, _get_fees, _apply_fees_and_rounding, _create_order). '
            'Inspect the module candidates log above to find the right name.'
        )

    # Capture the presale request into the thread-local so calculate_fee
    # can find the cart. Pretix fires these signals from its presale
    # middleware on every event-scoped page, including checkout/confirm
    # POSTs that create orders — so order placement inherits the same
    # request context.
    try:
        from pretix.presale.signals import process_request, process_response
    except (ImportError, AttributeError) as e:
        # Fail CLOSED for the fee patch: without request capture, a patched
        # calculate_fee would resolve every markup to $0 (revenue loss). We
        # return BEFORE patching calculate_fee, so Stripe keeps its native
        # fee. New Stripe orders still get the correct fiat price via the
        # _create_order bake wrapped above (independent of these signals);
        # only the chooser-preview label and the change-payment-method
        # markup are unavailable until this is fixed — hence ERROR, not
        # warning, so ops notices.
        log.error(
            'pretix_eth: presale signals not importable (%s); calculate_fee '
            'markup patch NOT installed (Stripe keeps native fee). New-order '
            'price-bake is unaffected.', e,
        )
        return

    # weak=False is required: these handlers are defined inside this
    # install function and would otherwise be garbage-collected the moment
    # the function returns (Django signals default to weak refs). Without
    # this, the signal fires correctly but our receiver is no longer
    # alive to handle it — symptom was an empty thread-local on every
    # calculate_fee call even though the signal was firing fine.
    def _capture_request(sender, request, **kwargs):
        ctx.request = request
        log.debug('pretix_eth[req]: captured request for event=%s path=%s',
                  getattr(sender, 'slug', '?'), getattr(request, 'path', '?'))

    def _release_request(sender, request, response, **kwargs):
        ctx.request = None
        return response

    process_request.connect(
        _capture_request, weak=False,
        dispatch_uid='pretix_eth_fee_exempt_capture',
    )
    process_response.connect(
        _release_request, weak=False,
        dispatch_uid='pretix_eth_fee_exempt_release',
    )

    # Keep strong refs on the module so they survive function return
    # even if `weak=False` is ignored by some signal variant.
    globals()['_fee_exempt_capture'] = _capture_request
    globals()['_fee_exempt_release'] = _release_request
    globals()['_fee_exempt_ctx'] = ctx

    log.info(
        'pretix_eth[install]: receivers connected (process_request has %d total receivers)',
        len(process_request.receivers),
    )

    # Request capture is now wired, so it's safe to patch calculate_fee: it
    # will always have a request/positions context to resolve the markup
    # from. Installed LAST on purpose (see the note above `orig_calc`).
    #
    # V73: patch the BASE class so every non-crypto (fiat) rail gets the card
    # markup, not just Stripe. Concrete providers inherit calculate_fee from
    # BasePaymentProvider (Stripe's StripeMethod does not override it), and the
    # wrapper (a) exempts the crypto rail via _is_crypto_provider_ident and
    # (b) preserves each provider's native configured fee when there is no
    # dual-pricing markup, so patching the base class can't wipe legitimate
    # payment fees elsewhere. Idempotent against worker reloads.
    if not getattr(BasePaymentProvider.calculate_fee, '_ped_fiat_wrapped', False):
        wrapped_calc = _make_wrapped_calc(orig_calc)
        wrapped_calc._ped_fiat_wrapped = True
        BasePaymentProvider.calculate_fee = wrapped_calc
        log.info('pretix_eth[install]: per-item markup patched calculate_fee on BasePaymentProvider '
                 '(all non-crypto rails; crypto exempt)')


def _install_stripe_mail_render():
    """Add a default `order_pending_mail_render` on Pretix's StripeMethod
    so the `{payment_info}` placeholder in the order-paid email is
    populated for Stripe orders the same way it is for crypto orders.

    Pretix's `BasePaymentProvider.order_pending_mail_render` returns an
    empty string, and Pretix-Stripe doesn't override it — which leaves
    the `{payment_info}` block empty in Stripe order emails. This patch
    fills it with a small recap (method name, amount, Stripe reference)
    so buyers get the same email shape regardless of how they paid.

    Skipped if Stripe isn't installed, or if the operator's email
    template doesn't include `{payment_info}` (in which case this just
    becomes a no-op renderer).
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from pretix.plugins.stripe.payment import StripeMethod
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: Stripe payment plugin not importable (%s); '
            'order-paid email payment-info recap disabled for Stripe.',
            e,
        )
        return

    # Don't double-patch if a real implementation exists. `BasePaymentProvider`
    # provides a no-op; we replace that, but if a concrete subclass already
    # has its own implementation we respect it.
    own_impl = StripeMethod.__dict__.get('order_pending_mail_render')
    if own_impl is not None:
        log.info('pretix_eth[install]: StripeMethod already implements '
                 'order_pending_mail_render — leaving it alone')
        return

    def _stripe_order_pending_mail_render(self, order, payment):
        # Build a minimal recap mirroring the shape of the crypto recap
        # (one fact per line, blank line between, since Pretix's email
        # markdown collapses single newlines).
        log.info(
            'pretix_eth[mail]: stripe order_pending_mail_render called '
            'order=%s payment=%s provider=%s',
            getattr(order, 'code', '?'),
            getattr(payment, 'pk', '?'),
            getattr(payment, 'provider', '?'),
        )
        info = payment.info_data or {}
        lines = []

        # Friendly method name — "Credit Card via Stripe", "SEPA Direct
        # Debit", etc. — falls back to verbose_name.
        try:
            method = str(getattr(self, 'method_name', None) or self.verbose_name)
            if method:
                lines.append('Payment method: {}'.format(method))
        except Exception:
            pass

        # Amount + currency
        try:
            from pretix.base.templatetags.money import money_filter
            lines.append('Amount: {}'.format(money_filter(payment.amount, order.event.currency)))
        except Exception:
            try:
                lines.append('Amount: {} {}'.format(payment.amount, order.event.currency))
            except Exception:
                pass

        # Card last4 if present (helps buyers identify the charge on their
        # statement); Stripe stores this under various keys depending on
        # API version, so we check a few.
        card = info.get('source') or info.get('charges') or {}
        if isinstance(card, dict):
            last4 = (
                card.get('last4')
                or ((card.get('card') or {}).get('last4'))
                or ((card.get('payment_method_details') or {}).get('card') or {}).get('last4')
            )
            brand = (
                card.get('brand')
                or ((card.get('card') or {}).get('brand'))
                or ((card.get('payment_method_details') or {}).get('card') or {}).get('brand')
            )
            if last4:
                bits = []
                if brand:
                    bits.append(str(brand).title())
                bits.append('ending in {}'.format(last4))
                lines.append('Card: {}'.format(' '.join(bits)))

        # Stripe reference (PaymentIntent / charge ID) for support lookup.
        ref = info.get('id') or info.get('payment_intent') or info.get('charge')
        if ref:
            lines.append('Stripe reference: {}'.format(ref))

        return '\n\n'.join(lines)

    StripeMethod.order_pending_mail_render = _stripe_order_pending_mail_render
    log.info('pretix_eth[install]: added order_pending_mail_render to StripeMethod')


def _install_payment_info_autofill():
    """Make the `{payment_info}` placeholder in the order-paid email work
    for providers (like Stripe) that don't explicitly pass `mail_text=`
    when calling `OrderPayment.confirm()`.

    Pretix's `_send_paid_mail` (`base/models/orders.py:2021`) wires the
    `mail_text` arg from confirm() into `payment_info=` of the email
    context. Pretix's `{payment_info}` placeholder has two registrations:
    one that auto-renders from `payments` (only used when `mail_text`
    isn't in context), and one that returns `mail_text` verbatim. The
    second wins whenever `mail_text` is in the context, even if it's
    empty — so the auto-render variant never fires for paid-mail.

    Our existing crypto verify code calls `confirm(mail_text=...)`
    explicitly. Pretix-Stripe (`plugins/stripe/payment.py:1028`) calls
    `confirm()` with no mail_text → the placeholder ends up empty in
    the buyer's email even though we already patched StripeMethod's
    `order_pending_mail_render`.

    The wrap here computes mail_text from the provider's
    `order_pending_mail_render` when the caller didn't supply one,
    closing the gap.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from pretix.base.models.orders import OrderPayment
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: OrderPayment not importable (%s); '
            'payment_info auto-fill disabled.', e,
        )
        return

    orig_confirm = OrderPayment.confirm

    def _wrapped_confirm(self, *args, **kwargs):
        # Only auto-fill when the caller passed nothing (or an empty
        # string). Crypto already supplies its own mail_text; we don't
        # want to overwrite it.
        if not kwargs.get('mail_text'):
            try:
                provider = self.payment_provider
                if provider:
                    result = ''
                    try:
                        result = provider.order_pending_mail_render(self.order, self) or ''
                    except TypeError:
                        # Older Pretix signature: (order) only, no payment.
                        try:
                            result = provider.order_pending_mail_render(self.order) or ''
                        except Exception:
                            result = ''
                    if result and result.strip():
                        kwargs['mail_text'] = result
                        log.info(
                            'pretix_eth[mail]: auto-filled mail_text on confirm() '
                            'order=%s payment=%s provider=%s len=%d',
                            self.order.code, self.pk, self.provider, len(result),
                        )
            except Exception as e:
                log.debug('pretix_eth[mail]: auto-fill skipped: %s', e)
        return orig_confirm(self, *args, **kwargs)

    OrderPayment.confirm = _wrapped_confirm
    log.info('pretix_eth[install]: wrapped OrderPayment.confirm for {payment_info} auto-fill')
