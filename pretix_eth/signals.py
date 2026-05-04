from django.dispatch import receiver

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import process_response
from pretix.base.signals import register_payment_providers


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
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response


@receiver(register_payment_providers, dispatch_uid='wc_register_payment')
def register_payment_provider(sender, **kwargs):
    from .payment import WalletConnectPayment
    return WalletConnectPayment


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
