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
        from . import signals  # noqa
        _install_order_placed_email_suppressor()
        _install_fiat_provider_restrictor()
        _install_fiat_fee_name_decoration()


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
        # OrderPayment row at placement time.
        try:
            payment = order.payments.first()
        except Exception:
            return False
        if not payment or payment.provider != 'walletconnect':
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
    """Monkey-patch `pretix.plugins.stripe.payment.StripeMethod.is_allowed`
    so that Stripe (and every concrete payment method that inherits from it
    — card, SEPA, etc.) is hidden whenever the current cart or order
    contains an item listed in the event's `payment_walletconnect_fiat_blocked_items`
    setting.

    Why monkey-patch: Pretix has no first-class "this item bans this
    payment method" config. Sales-channels could express it but would
    force buyers onto a separate URL. Overriding `is_allowed` covers
    BOTH checkout flows (cart → pay, and order → change payment method)
    with one hook that runs server-side, so the rule can't be bypassed
    by hand-crafting a URL.

    If Stripe's plugin is missing or has been renamed in a future Pretix
    version, the import fails cleanly and the admin checklist becomes a
    no-op (we log a warning) rather than crashing the worker.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from pretix.plugins.stripe.payment import StripeMethod
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: Stripe payment plugin not importable (%s); '
            'the "Items that block fiat payment" admin checklist will have no effect.',
            e,
        )
        return

    orig_is_allowed = StripeMethod.is_allowed

    def _is_blocked_for_fiat(provider, request):
        event = provider.event
        # Setting is a CharField holding comma-separated IDs (e.g. "145, 146").
        # We tolerate stray whitespace / trailing commas; anything non-integer
        # is silently dropped so a typo doesn't block all fiat.
        raw = event.settings.get(
            'payment_walletconnect_fiat_blocked_items',
            as_type=str,
            default='',
        ) or ''
        blocked_ids = set()
        for token in raw.split(','):
            token = token.strip()
            if not token:
                continue
            try:
                blocked_ids.add(int(token))
            except (TypeError, ValueError):
                continue
        if not blocked_ids:
            return False

        from pretix.base.models import CartPosition, OrderPosition

        # Cart flow — buyer is in checkout, no order yet.
        # Pretix's helper is `get_or_create_cart_id(request, create=False)`
        # (returns None when no cart exists). Falls back to the session key
        # `current_cart_event_<pk>` if the import path ever changes.
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

        if cart_id:
            matched = CartPosition.objects.filter(
                cart_id=cart_id, event=event, item_id__in=blocked_ids,
            ).values_list('item_id', flat=True)
            matched_list = list(matched)
            if matched_list:
                log.info(
                    'pretix_eth: fiat blocked for cart=%s event=%s (matched items %s in blocked set %s)',
                    cart_id, event.slug, matched_list, sorted(blocked_ids),
                )
                return True

        # Order re-pay flow — order code lives in the URL kwargs.
        try:
            match = getattr(request, 'resolver_match', None)
            order_code = match.kwargs.get('order') if match else None
        except Exception:
            order_code = None
        if order_code:
            matched = OrderPosition.objects.filter(
                order__code=order_code, order__event=event, item_id__in=blocked_ids,
            ).values_list('item_id', flat=True)
            matched_list = list(matched)
            if matched_list:
                log.info(
                    'pretix_eth: fiat blocked for order=%s event=%s (matched items %s in blocked set %s)',
                    order_code, event.slug, matched_list, sorted(blocked_ids),
                )
                return True

        return False

    def _wrapped_is_allowed(self, request, total=None):
        if _is_blocked_for_fiat(self, request):
            return False
        return orig_is_allowed(self, request, total)

    StripeMethod.is_allowed = _wrapped_is_allowed


def _install_fiat_fee_name_decoration():
    """Append the configured Stripe additional-fee (percentage and/or
    absolute amount) to the buyer-facing payment-method label, so the
    chooser shows e.g. "+3% · Credit Card" before the buyer commits
    to fiat. The fee values come from Pretix's standard payment-fee
    settings (`_fee_percent`, `_fee_abs`) configured per-method under
    *Event → Settings → Payment → Stripe*.

    The patch walks every concrete subclass of `StripeMethod` because
    Pretix-Stripe defines `public_name` per-method (card vs SEPA vs
    iDEAL …). For each class we wrap whatever `public_name` it inherits
    or defines, so the original label is preserved when no fee is set.

    No-op for methods with both fee fields at 0. Fails closed on
    import errors — original labels remain unchanged.
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

    def _make_decorated(original_getter):
        def _decorated(self):
            try:
                base = original_getter(self)
            except Exception:
                base = str(self.verbose_name)
            try:
                fee_pct = self.settings.get('_fee_percent', as_type=Decimal, default=Decimal('0')) or Decimal('0')
                fee_abs = self.settings.get('_fee_abs', as_type=Decimal, default=Decimal('0')) or Decimal('0')
            except Exception:
                return base
            # Each bit is a bare amount ("20%", "1.50 USD"); we glue them
            # with " + " and prefix the whole block with one "+" so a
            # combined pct+abs fee reads as "+20% + 1.50 USD" rather than
            # the awkward "+20% + +1.50 USD".
            bits = []
            if fee_pct > 0:
                # Strip trailing zeros so "3.00" displays as "3".
                pct_str = format(fee_pct.normalize(), 'f') if fee_pct == fee_pct.to_integral() else format(fee_pct, 'f').rstrip('0').rstrip('.')
                bits.append(f'{pct_str}%')
            if fee_abs > 0:
                currency = (getattr(self.event, 'currency', '') or '').strip()
                abs_str = format(fee_abs, 'f').rstrip('0').rstrip('.')
                bits.append(f'{abs_str} {currency}'.strip())
            if not bits:
                return base
            # Front-place the markup so Stripe's auto-appended wallet
            # list ("…, Google Pay") doesn't end up after our suffix.
            return f'+{" + ".join(bits)} · {base}'
        return _decorated

    def _patch_class(cls):
        own = cls.__dict__.get('public_name')
        if isinstance(own, property) and own.fget:
            getter = own.fget
        else:
            # Inherited property — resolve via MRO.
            inherited = inspect.getattr_static(cls, 'public_name', None)
            getter = inherited.fget if isinstance(inherited, property) and inherited.fget else (lambda self: str(self.verbose_name))
        cls.public_name = property(_make_decorated(getter))

    # Patch the base + every subclass currently loaded. Subclasses can
    # define their own `public_name`, so patching the base alone isn't
    # enough.
    targets = [StripeMethod] + list(StripeMethod.__subclasses__())
    for cls in targets:
        try:
            _patch_class(cls)
        except Exception as e:
            log.warning('pretix_eth: failed to decorate %s.public_name: %s', cls.__name__, e)
