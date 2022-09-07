from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django.template.loader import get_template

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import (
    html_head,
    process_response,
)
from pretix.base.signals import (
    logentry_display,
    register_payment_providers,
    register_data_exporters,
)

from pretix.control.signals import (
    event_dashboard_widgets,
    nav_event_settings,
)
from .exporter import EthereumOrdersExporter
from . import models


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
            "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='",
            "'sha256-O+AX3tWIOimhuzg+lrMfltcdtWo7Mp2Y9qJUkE6ysWE='",
        ],
        # Chrome correctly errors out without this CSP
        'connect-src': [
            "https://registry.walletconnect.com/",
            "https://*.bridge.walletconnect.org/",
            "wss://*.bridge.walletconnect.org/",
            "https://*.infura.io/",
            "wss://*.infura.io/",
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response


@receiver(html_head, dispatch_uid="payment_eth_add_question_type_javascript")
def add_question_type_javascript(sender, request, **kwargs):
    # TODO: enable js only when question is asked
    # url = resolve(request.path_info)
    template = get_template('pretix_eth/question_type_javascript.html')
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
