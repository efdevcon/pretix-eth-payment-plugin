from django.dispatch import receiver
from django.template.loader import get_template

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import (
    html_head,
    process_response,
)
from pretix.base.signals import (
    register_payment_providers,
    register_data_exporters,
)

@receiver(process_response, dispatch_uid="checkout_add_csp")
def checkout_add_csp(sender, request, response, **kwargs):
    h = {}
    if 'Content-Security-Policy' in response:
        h = _parse_csp(response['Content-Security-Policy'])
    _merge_csp(h, {
        'style-src': [
            'https://fonts.googleapis.com',
            "'unsafe-inline'"
        ],
        'img-src': [
            "blob: data:",
            "https://daimo.com",
            "https://*.daimo.com",
            "https://assets.coingecko.com"
        ],
        'script-src': [
            # unsafe-inline/eval required for webpack bundles (we cannot know names in advance).
            "'unsafe-inline'",
            "'unsafe-eval'"
        ],
        'font-src': [
            "https://fonts.gstatic.com"
        ],
        'frame-src': [
            'https://verify.walletconnect.org',
            'https://verify.walletconnect.com'
        ],
        # Chrome correctly errors out without this CSP
        'connect-src': [
            "https://*.daimo.xyz",
            "https://*.daimo.com",
            "https://cloudflare-eth.com/",
            "wss://*.walletconnect.org",
            "https://pulse.walletconnect.org",
            "https://assets.coingecko.com",
            "https://*.merkle.io",
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response


@receiver(register_payment_providers, dispatch_uid="payment_eth")
def register_payment_provider(sender, **kwargs):
    from .payment import DaimoPay
    return DaimoPay


@receiver(register_data_exporters, dispatch_uid='single_event_eth_orders')
def register_data_exporter(sender, **kwargs):
    from .exporter import EthereumOrdersExporter
    return EthereumOrdersExporter
