from django.dispatch import receiver

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import process_response
from pretix.base.signals import register_payment_providers, register_text_placeholders
from pretix.base.services.placeholders import SimpleFunctionalTextPlaceholder


@receiver(process_response, dispatch_uid='wc_checkout_csp')
def add_wc_csp(sender, request, response, **kwargs):
    """Inject CSP directives needed for WalletConnect, AppKit, Alchemy RPC, and public RPCs."""
    h = {}
    if 'Content-Security-Policy' in response:
        h = _parse_csp(response['Content-Security-Policy'])
    _merge_csp(h, {
        'style-src': ["'unsafe-inline'"],
        'img-src': [
            'blob: data:',
            'https://*.walletconnect.com',
            'https://*.reown.com',
        ],
        'script-src': [
            "'unsafe-inline'",
            "'unsafe-eval'",
        ],
        'font-src': [
            'https://fonts.gstatic.com',
            'https://fonts.reown.com',
        ],
        'frame-src': [
            'https://verify.walletconnect.org',
            'https://verify.walletconnect.com',
            'https://*.walletconnect.org',
        ],
        'connect-src': [
            'https://*.walletconnect.org',
            'https://*.walletconnect.com',
            'wss://relay.walletconnect.org',
            'wss://relay.walletconnect.com',
            'wss://*.walletconnect.org',
            'https://pulse.walletconnect.org',
            'https://*.reown.com',
            'https://*.alchemy.com',
            'https://*.publicnode.com',
            'https://api.web3modal.org',
            'https://*.web3modal.org',
            'https://*.coinbase.com',
            # Safe Transaction Service (multisig detection + safeTxHash /
            # safeMessageHash polling). Required only when an event admin
            # opts in via `safe_payments_enabled`; harmless to allowlist
            # globally since the bundle won't call it otherwise.
            'https://*.safe.global',
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response


@receiver(register_payment_providers, dispatch_uid='wc_register_payment')
def register_payment_provider(sender, **kwargs):
    from .payment import WalletConnectPayment
    return WalletConnectPayment


@receiver(register_text_placeholders, dispatch_uid='wc_secret_placeholder')
def register_order_secret_placeholder(sender, **kwargs):
    """Expose `{secret}` as a mail placeholder. Pretix's stock list includes
    `{code}` and `{url}` but not the bare order secret. Useful for operators
    who want to compose URLs inside the email template directly."""
    return SimpleFunctionalTextPlaceholder(
        'secret',
        ['order'],
        lambda order: order.secret,
        sample=lambda event: 'a1b2c3d4e5f6g7h8',
    )


@receiver(register_text_placeholders, dispatch_uid='wc_url_override')
def register_url_override(sender, **kwargs):
    """Override the stock `{url}` placeholder when the operator has configured
    a `frontend_order_url_template` on the WalletConnect plugin settings.

    Pretix's default `{url}` (in `pretix.base.services.placeholders`) builds
    a presale self-service order URL on Pretix's own domain. Operators
    running a separate FE (devcon-next) want emails to link into the FE's
    order page instead. Last-write-wins on placeholder identifier — plugin
    signals are dispatched after core, so our `{url}` shadows the default
    when this setting is non-empty.

    The template supports `{code}` and `{secret}` substitution. Example:
        https://devcon.org/en/tickets/store/order/{code}/{secret}/
    """
    from .payment import WalletConnectPayment
    provider = WalletConnectPayment(sender)
    template = (provider.settings.get('frontend_order_url_template') or '').strip()
    if not template:
        return []  # no override → Pretix default `{url}` wins
    return SimpleFunctionalTextPlaceholder(
        'url',
        ['order', 'event'],
        lambda order, event: (
            template.replace('{code}', order.code).replace('{secret}', order.secret)
        ),
        sample=lambda event: (
            template.replace('{code}', 'CODEX1').replace('{secret}', 'a1b2c3d4e5f6g7h8')
        ),
    )


try:
    from pretix.base.signals import periodic_task

    @receiver(periodic_task, dispatch_uid='pretix_eth_x402_cleanup')
    def register_x402_cleanup(sender, **kwargs):
        # Runs every hour via Pretix's built-in periodic_task signal
        from pretix_eth.x402.tasks import cleanup_expired_pending_task, cleanup_verify_attempts_task
        cleanup_expired_pending_task.apply_async()
        cleanup_verify_attempts_task.apply_async()
except ImportError:
    # Fallback: no periodic scheduling (dev/test environments)
    pass
