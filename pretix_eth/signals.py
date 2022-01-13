import logging
import json

from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django.template.loader import get_template

from django_scopes import scopes_disabled, scope

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import (
    html_head,
    process_response,
)
from pretix.base.models.event import Event
from pretix.base.signals import (
    logentry_display,
    register_payment_providers,
    register_data_exporters,
    periodic_task,
)
from pretix.control.signals import (
    event_dashboard_widgets,
    nav_event_settings,
)
from pretix.helpers.periodic import minimum_interval
from .exporter import EthereumOrdersExporter
from . import models
from .network.tokens import IToken, all_token_and_network_ids_to_tokens


NUM_WIDGET = '<div class="numwidget"><span class="num">{num}</span><span class="text">{text}</span></div>'  # noqa: E501


@receiver(periodic_task)
@scopes_disabled()
@minimum_interval(minutes_after_success=1)
def confirm_payments(sender, **kwargs):
    with scope(organizer=None):
        events = Event.objects.all()

    for event in events:
        confirm_payments_for_event(event)

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
            "wss://bridge.walletconnect.org/",
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


@receiver(event_dashboard_widgets)
def address_count_widget(sender, lazy=False, **kwargs):
    total_address = len(models.WalletAddress.objects.all().for_event(sender))
    unused_addresses = len(
        models.WalletAddress.objects.get_queryset().unused().for_event(sender)
    )
    used_addresses = total_address - unused_addresses
    return [
        {
            "content": None
            if lazy
            else NUM_WIDGET.format(
                num="{}/{}".format(used_addresses, total_address),
                text=_("Used/Total Addresses"),
            ),
            # value for lazy must be a fixed string.
            # str(lazy) or any if-else statement won't work.
            "lazy": "lazy",
            "display_size": "small",
            "priority": 100,
        }
    ]


@receiver(register_payment_providers, dispatch_uid="payment_eth")
def register_payment_provider(sender, **kwargs):
    from .payment import Ethereum
    return Ethereum


@receiver(nav_event_settings, dispatch_uid='pretix_eth_nav_wallet_address_upload')
def navbar_wallet_address_upload(sender, request, **kwargs):
    url = resolve(request.path_info)
    return [{
        'label': _('Wallet address upload'),
        'url': reverse('plugins:pretix_eth:wallet_address_upload', kwargs={
            'event': request.event.slug,
            'organizer': request.organizer.slug,
        }),
        'active': (
            url.namespace == 'plugins:pretix_eth'
            and (
                url.url_name == 'wallet_address_upload'
                or url.url_name == 'wallet_address_upload_confirm'
            )
        ),
    }]


@receiver(signal=logentry_display)
def wallet_address_upload_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type == 'pretix_eth.wallet_address_upload':
        data = logentry.parsed_data
        return _(
            'Uploaded {file_address_count} addresses '
            'with {new_address_count} new addresses '
            'and {existing_address_count} existing addresses.'
        ).format(
            file_address_count=data['file_address_count'],
            new_address_count=data['new_address_count'],
            existing_address_count=data['existing_address_count'],
        )


@receiver(register_data_exporters, dispatch_uid='single_event_eth_orders')
def register_data_exporter(sender, **kwargs):
    return EthereumOrdersExporter

# helper methods
logger = logging.getLogger(__name__)

def confirm_payments_for_event(event: Event):
    logger.info(f"Event name - {event.name}")

    unconfirmed_addresses = (
        models.WalletAddress.objects.all().for_event(event).unconfirmed_orders()
    )

    for wallet_address in unconfirmed_addresses:
        hex_address = wallet_address.hex_address

        order_payment = wallet_address.order_payment
        rpc_urls = json.loads(
            order_payment.payment_provider.settings.NETWORK_RPC_URL
        )
        full_id = order_payment.full_id

        info = order_payment.info_data
        token: IToken = all_token_and_network_ids_to_tokens[info["currency_type"]]
        expected_network_id = token.NETWORK_IDENTIFIER
        expected_network_rpc_url_key = f"{expected_network_id}_RPC_URL"
        network_rpc_url = None

        if expected_network_rpc_url_key in rpc_urls:
            network_rpc_url = rpc_urls[expected_network_rpc_url_key]
        else:
            logger.warning(
                f"No RPC URL configured for {expected_network_id}. Skipping..."
            )
            continue

        expected_amount = info["amount"]

        # Get balance.
        balance = token.get_balance_of_address(hex_address, network_rpc_url)

        if balance > 0:
            logger.info(f"Payments found for {full_id} at {hex_address}:")
            if balance < expected_amount:
                logger.warning(
                    f"  * Expected payment of at least {expected_amount} {token.TOKEN_SYMBOL}"
                )
                logger.warning(
                    f"  * Given payment was {balance} {token.TOKEN_SYMBOL}"
                )
                logger.warning(f"  * Skipping")  # noqa: F541
                continue
            logger.info(f"  * Confirming order payment {full_id}")
            with scope(organizer=None):
                order_payment.confirm()
        else:
            logger.info(f"No payments found for {full_id}")
