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
            "'sha256-9h9aPS509wv9tZVxhu0nafBWlh+iaLnprlcvGgGBrdc='",
            "'sha256-DcyKFer0/PNr8zSoqGvI+uLTvhcd7+ZrM8+TmG2QAvM='",
            "'sha256-tExE+c+cPIPjfUjwNtUK/J5aPbrI03LPmDpjHbcju/I='",
            "'sha256-PuESmRo5xLKq9p5zvWn/yHwOcA+VaQ0L6ObRcRKsl3g='",
            "'sha256-/Y8sOmVZLE8kYkmzpX15FodnMH6ygvqAz1FyNpY8qoo='",
            "'sha256-VMErMRuzD9JGQOwDtb0NWk6Ei1jibuo0S7h0b3Zt5Nw='",
            "'sha256-thB/1uQ6hZv+vTQDSxOw21131dHhE475xakO9wp4pxo='",
            "'sha256-4CSX0cSvsqdXksjA6mWUlZWOxhEmilc7TqCXOuzQjd8='",
            "'sha256-QIjW/+aUzfg58HcITJNHkkCTGmLovNUIQbL+Zq2TsIE='",
            "https://*.bridge.walletconnect.org/",
        ],
        'img-src': [
            'https://registry.walletconnect.com',
            "https://explorer-api.walletconnect.com/",
            "https://*.bridge.walletconnect.org/",
        ],
        'script-src': [
            "https://unpkg.com/",
            "https://cdn.jsdelivr.net"
        ],
        # Chrome correctly errors out without this CSP
        'connect-src': [
            "https://zksync2-mainnet.zksync.io/",
            "https://rpc.ankr.com/eth_goerli",
            "https://registry.walletconnect.com/",
            "https://*.bridge.walletconnect.org/",
            "wss://*.bridge.walletconnect.org/",
            "https://bridge.walletconnect.org/",
            "wss://bridge.walletconnect.org/",
            "https://explorer-api.walletconnect.com/",
            "https://*.infura.io/",
            "wss://*.infura.io/",
            "https://rpc.walletconnect.com/",
            "https://cloudflare-eth.com/",
            "wss://www.walletlink.org/",
            "https://www.sepoliarpc.space/",
            "https://rpc.sepolia.org/",
            "https://arb1.arbitrum.io/rpc",
            "https://mainnet.optimism.io/"
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
