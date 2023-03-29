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

from .exporter import EthereumOrdersExporter


NUM_WIDGET = '<div class="numwidget"><span class="num">{num}</span><span class="text">{text}</span></div>'  # noqa: E501


@receiver(process_response, dispatch_uid="payment_eth_add_question_type_csp")
def signal_process_response(sender, request, response, **kwargs):
    # TODO: enable js only when question is asked
    # url = resolve(request.path_info)
    h = {}
    if 'Content-Security-Policy' in response:
        h = _parse_csp(response['Content-Security-Policy'])
    _merge_csp(h, {
        'style-src': [
            "'unsafe-inline'"
        ],
        'img-src': [
            'https://registry.walletconnect.com',
            "https://explorer-api.walletconnect.com",
            "https://*.bridge.walletconnect.org",
        ],
        'script-src': [
            # unsafe-inline/eval required for webpack bundles (we cannot know names in advance).
            "'unsafe-inline'",
            "'unsafe-eval'"
        ],
        # Chrome correctly errors out without this CSP
        'connect-src': [
            "wss://relay.walletconnect.com",
            "https://explorer-api.walletconnect.com",
            "https://rpc.walletconnect.com",
            "https://zksync2-mainnet.zksync.io/",
            "https://rpc.ankr.com/eth_goerli",
            "https://registry.walletconnect.com/",
            "https://*.bridge.walletconnect.org/",
            "wss://*.bridge.walletconnect.org/",
            "https://bridge.walletconnect.org/",
            "wss://bridge.walletconnect.org/",
            "https://*.infura.io/",
            "wss://*.infura.io/",
            "https://cloudflare-eth.com/",
            "wss://www.walletlink.org/",
            "https://www.sepoliarpc.space/",
            "https://rpc.sepolia.org/",
            "https://arb1.arbitrum.io/rpc",
            "https://mainnet.optimism.io/",
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response


@receiver(html_head,
          dispatch_uid="payment_eth_add_web3modal_css_and_javascript")
def add_web3modal_css_and_javascript(sender, request, **kwargs):
    # TODO: enable js only when question is asked
    # url = resolve(request.path_info)
    template = get_template('pretix_eth/web3modal_css_and_javascript.html')
    context = {
        'event': sender,
    }
    return template.render(context)


@receiver(register_payment_providers, dispatch_uid="payment_eth")
def register_payment_provider(sender, **kwargs):
    from .payment import Ethereum
    return Ethereum


@receiver(register_data_exporters, dispatch_uid='single_event_eth_orders')
def register_data_exporter(sender, **kwargs):
    return EthereumOrdersExporter
