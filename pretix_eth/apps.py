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
