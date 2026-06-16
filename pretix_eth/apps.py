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
        _install_fiat_markup_exemption()


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

        # Ignore add-on positions (addon_to NOT NULL) so a buyer adding a
        # restricted add-on to an unrelated main item doesn't change the
        # available payment methods. Add-ons follow their parent's rules.
        if cart_id:
            matched = CartPosition.objects.filter(
                cart_id=cart_id, event=event, item_id__in=blocked_ids,
                addon_to__isnull=True,
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
                addon_to__isnull=True,
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


def _current_cart_fully_exempt(event):
    """Returns True when every position in the buyer's current cart for
    `event` is in the event's `payment_walletconnect_fiat_markup_exempt_items`
    list. Used by the `public_name` decorator to suppress the misleading
    "+X%" prefix when the actual Stripe fee will be $0.

    Reads the active request from the thread-local that
    `_install_fiat_markup_exemption` populates via `process_request`.
    Returns False on any error / when the request or cart isn't available
    so we fail open (label keeps the prefix, matching the prior behaviour).
    """
    from decimal import Decimal
    ctx = globals().get('_fee_exempt_ctx')
    if ctx is None:
        return False
    request = getattr(ctx, 'request', None)
    if request is None:
        return False

    raw = event.settings.get(
        'payment_walletconnect_fiat_markup_exempt_items',
        as_type=str,
        default='',
    ) or ''
    exempt_ids = set()
    for tok in raw.split(','):
        tok = tok.strip()
        if not tok:
            continue
        try:
            exempt_ids.add(int(tok))
        except (TypeError, ValueError):
            continue
    if not exempt_ids:
        return False

    # Resolve cart_id the same way the fee patch does.
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
            return False
    if not cart_id:
        return False

    from pretix.base.models import CartPosition
    # Only consider base (non-addon) positions; add-ons inherit their
    # parent's payment treatment, so a non-exempt add-on shouldn't make
    # an otherwise-exempt cart look mixed.
    positions = CartPosition.objects.filter(
        cart_id=cart_id, event=event, addon_to__isnull=True,
    )
    item_ids = list(positions.values_list('item_id', flat=True))
    if not item_ids:
        return False
    # Fully exempt only when EVERY main-item position is in the exempt set.
    return all(iid in exempt_ids for iid in item_ids)


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

            # Suppress the markup prefix when the current cart is fully
            # exempt — otherwise the buyer sees "+20% · Credit card" but
            # actually pays $0 markup, which is misleading. We consult
            # the shared thread-local request set up by the markup
            # exemption installer; if the cart is fully covered by the
            # exempt list, skip the prefix.
            try:
                if _current_cart_fully_exempt(self.event):
                    return base
            except Exception:
                pass

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


def _install_fiat_markup_exemption():
    """Make Pretix's Stripe additional-fee opt out of selected items.

    Pretix's `BasePaymentProvider.calculate_fee(price)` only sees a
    scalar — no cart breakdown — and Pretix itself fans the fee
    calculation across at least four code paths (cart preview,
    PaymentStep.provider_forms chooser, CartMixin.current_selected_payments,
    order placement) that don't share a clean hook. Rather than wrap
    each call site we capture the current presale request via Pretix's
    `process_request` / `process_response` signals into a thread-local,
    then have the patched `StripeMethod.calculate_fee` look up the cart
    positions itself (from `request.session` → cart_id → CartPosition).
    Single sync point, covers every fee-calc path that runs during a
    buyer-side request.

    Order-placement and re-pay paths run inside the same request, so the
    thread-local is still populated. Admin-side recalculations (no
    presale request) fall through to the original markup — acceptable
    since the goal is the buyer experience.

    Stripe-only: hooks `StripeMethod` and its loaded subclasses. Other
    fiat providers keep their original fees.
    """
    import logging
    import threading
    from decimal import Decimal
    log = logging.getLogger(__name__)
    try:
        from pretix.plugins.stripe.payment import StripeMethod
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: Stripe payment plugin not importable (%s); '
            'fiat-markup exemption disabled.',
            e,
        )
        return

    # Thread-local stash for the current presale request. Set by the
    # process_request receiver below, cleared by process_response.
    ctx = threading.local()

    def _exempt_ids(event):
        raw = event.settings.get(
            'payment_walletconnect_fiat_markup_exempt_items',
            as_type=str,
            default='',
        ) or ''
        ids = set()
        for tok in raw.split(','):
            tok = tok.strip()
            if not tok:
                continue
            try:
                ids.add(int(tok))
            except (TypeError, ValueError):
                continue
        return ids

    def _exempt_subtotal_from_positions(event, positions, ids):
        """Compute exempt subtotal directly from an in-memory positions list.
        Used when we have positions but no live request (e.g. Celery
        order placement). Mirrors the DB query logic in
        `_exempt_subtotal_for`: a position is exempt if it's a main
        position whose item is in `ids`, OR an add-on attached to such
        a main position."""
        from decimal import Decimal as D
        # Build set of PKs of exempt main positions, by iterating once.
        exempt_main_pks = set()
        for p in positions:
            if getattr(p, 'addon_to_id', None) is None and getattr(p, 'item_id', None) in ids:
                pk = getattr(p, 'pk', None)
                if pk is not None:
                    exempt_main_pks.add(pk)
        if not exempt_main_pks:
            return D('0')
        total = D('0')
        for p in positions:
            pk = getattr(p, 'pk', None)
            addon_to = getattr(p, 'addon_to_id', None)
            if pk in exempt_main_pks or addon_to in exempt_main_pks:
                try:
                    total += D(str(getattr(p, 'price', 0) or 0))
                except Exception:
                    continue
        return total

    def _exempt_subtotal_for(event):
        ids = _exempt_ids(event)
        if not ids:
            log.info('pretix_eth[exempt]: event=%s no exempt items configured', getattr(event, 'slug', '?'))
            return Decimal('0')
        log.info('pretix_eth[exempt]: event=%s configured exempt_ids=%s', getattr(event, 'slug', '?'), sorted(ids))

        # PRIMARY path: positions stashed by the _apply_rounding_and_fees
        # wrap below. Works in Celery (order-placement) where no HTTP
        # request is active. Also covers HTTP paths that pass through
        # _apply_rounding_and_fees.
        positions = getattr(ctx, 'positions', None)
        if positions is not None:
            total = _exempt_subtotal_from_positions(event, positions, ids)
            log.info(
                'pretix_eth[exempt]: from-positions positions_count=%s exempt_total=%s',
                len(positions), total,
            )
            return total

        request = getattr(ctx, 'request', None)
        if request is None:
            log.info('pretix_eth[exempt]: no request and no positions in thread-local')
            return Decimal('0')

        # Resolve the active cart for this event.
        cart_id = None
        try:
            from pretix.presale.views.cart import get_or_create_cart_id
            cart_id = get_or_create_cart_id(request, create=False)
        except Exception as e:
            log.info('pretix_eth[exempt]: get_or_create_cart_id failed (%s)', e)
        if not cart_id:
            try:
                cart_id = request.session.get('current_cart_event_{}'.format(event.pk))
                log.info('pretix_eth[exempt]: fell back to session key, cart_id=%s', cart_id)
            except Exception as e:
                log.info('pretix_eth[exempt]: session lookup failed (%s)', e)
                cart_id = None
        if not cart_id:
            log.info('pretix_eth[exempt]: no cart_id resolved for event=%s', getattr(event, 'slug', '?'))
            return Decimal('0')

        from django.db.models import Q, Sum
        from pretix.base.models import CartPosition
        # Add-ons inherit their parent's payment treatment. Find the PK
        # of every exempt MAIN position, then sum prices of (those mains
        # + their attached add-ons). Without this, an exempt main with
        # paid add-ons under-counts as exempt and the Stripe fee comes
        # out non-zero — which mismatches the chooser preview and
        # triggers Pretix's "order total has changed" error at confirm.
        qs = CartPosition.objects.filter(cart_id=cart_id, event=event)
        exempt_main_pks = list(qs.filter(
            addon_to__isnull=True, item_id__in=ids,
        ).values_list('pk', flat=True))
        if not exempt_main_pks:
            log.info('pretix_eth[exempt]: cart=%s no exempt main items', cart_id)
            return Decimal('0')
        exempt_qs = qs.filter(
            Q(pk__in=exempt_main_pks) | Q(addon_to_id__in=exempt_main_pks)
        )
        matched_items = list(exempt_qs.values_list('item_id', flat=True))
        agg = exempt_qs.aggregate(s=Sum('price'))
        total = agg.get('s') or Decimal('0')
        log.info(
            'pretix_eth[exempt]: cart=%s exempt_main_pks=%s matched_items=%s exempt_total=%s',
            cart_id, exempt_main_pks, matched_items, total,
        )
        return total

    def _make_wrapped_calc(orig):
        def _wrapped(self, price):
            cls_name = type(self).__name__
            log.info('pretix_eth[calc]: %s.calculate_fee(price=%s) called', cls_name, price)
            try:
                exempt = _exempt_subtotal_for(self.event)
            except Exception as e:
                log.warning('pretix_eth[calc]: fee-exempt calc failed: %s', e)
                return orig(self, price)
            if exempt <= Decimal('0'):
                log.info('pretix_eth[calc]: %s no exempt items, original fee applies', cls_name)
                return orig(self, price)
            try:
                price_d = price if isinstance(price, Decimal) else Decimal(str(price))
            except Exception:
                return orig(self, price)
            adjusted = max(Decimal('0'), price_d - exempt)
            result = orig(self, adjusted)
            log.info(
                'pretix_eth[calc]: %s adjusted price=%s exempt=%s adjusted=%s -> fee=%s',
                cls_name, price_d, exempt, adjusted, result,
            )
            return result
        return _wrapped

    # CRITICAL: only patch the base class. Pretix-Stripe subclasses
    # (StripeCC, StripeSEPADirectDebit, …) all inherit calculate_fee
    # from StripeMethod without overriding it. If we ALSO patched each
    # subclass, the orig we captured for subclass N would already be the
    # wrapped version from N-1, causing the cart-exempt subtraction to
    # run twice on a single call — which broke mixed carts (e.g. an OSS
    # exempt + a non-exempt GA returned fee=0 instead of fee on the GA
    # portion, triggering Pretix's "order total has changed" mismatch
    # at confirm).
    orig_calc = StripeMethod.calculate_fee
    StripeMethod.calculate_fee = _make_wrapped_calc(orig_calc)
    log.info('pretix_eth[install]: fiat-markup exemption patched calculate_fee on StripeMethod (subclasses inherit)')

    # ALSO wrap _apply_rounding_and_fees (the function Pretix calls
    # from both cart preview and order placement). This stashes the
    # positions list directly so calculate_fee can compute the exempt
    # subtotal without needing the HTTP request — critical for the
    # Celery-driven order-placement path where the presale `process_request`
    # signal never fires and ctx.request would be None.
    try:
        from pretix.base.services import orders as orders_svc
        orig_apply = getattr(orders_svc, '_apply_rounding_and_fees', None)
    except ImportError:
        orig_apply = None
    if orig_apply is not None:
        def _wrapped_apply(*args, **kwargs):
            positions = kwargs.get('positions')
            if positions is None and args:
                positions = args[0]
            prev = getattr(ctx, 'positions', None)
            ctx.positions = positions
            try:
                return orig_apply(*args, **kwargs)
            finally:
                ctx.positions = prev
        orders_svc._apply_rounding_and_fees = _wrapped_apply
        log.info('pretix_eth[install]: wrapped orders._apply_rounding_and_fees for Celery-side fee calc')

    # Capture the presale request into the thread-local so calculate_fee
    # can find the cart. Pretix fires these signals from its presale
    # middleware on every event-scoped page, including checkout/confirm
    # POSTs that create orders — so order placement inherits the same
    # request context.
    try:
        from pretix.presale.signals import process_request, process_response
    except (ImportError, AttributeError) as e:
        log.warning(
            'pretix_eth: presale signals not importable (%s); '
            'fiat-markup exemption will not run.', e,
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
