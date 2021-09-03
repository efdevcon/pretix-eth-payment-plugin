import logging
import time
from collections import OrderedDict
import json

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from pretix.base.models import (
    OrderPayment,
    OrderRefund,
)
from pretix.base.payment import BasePaymentProvider

from eth_utils import from_wei

from .models import WalletAddress
from .network.tokens import (
    IToken,
    registry,
    all_network_verbose_names_to_ids,
    all_token_and_network_ids_to_tokens,
    token_verbose_name_to_token_network_id
)

logger = logging.getLogger(__name__)

RESERVED_ORDER_DIGITS = 5


def truncate_wei_value(value: int, digits: int) -> int:
    multiplier = 10 ** digits
    return int(round(value / multiplier) * multiplier)

class Ethereum(BasePaymentProvider):
    identifier = "ethereum"
    verbose_name = _("ETH or DAI")
    public_name = _("ETH or DAI")

    @property
    def settings_form_fields(self):
        form_fields = OrderedDict(
            list(super().settings_form_fields.items())
            + [
                (
                    "TOKEN_RATES",
                    forms.JSONField(
                        label=_("Token Rate"),
                        help_text=_(
                            "JSON field with key=<TOKEN_SYMBOL>_RATE and value = amount for a token in USD. E.g. 'ETH_RATE':4000."
                        ),
                    ),
                ),
                # Based on pretix source code, MultipleChoiceField breaks if settings doesnt start with an "_". No idea how this works...
                (
                    "_NETWORKS",
                    forms.MultipleChoiceField(
                        label=_("Networks"),
                        choices=[
                            (
                                all_network_verbose_names_to_ids[network_verbose_name],
                                network_verbose_name,
                            )
                            for network_verbose_name in all_network_verbose_names_to_ids
                        ],
                        help_text=_(
                            "The networks to be configured for crypto payments"
                        ),
                        widget=forms.CheckboxSelectMultiple(
                            attrs={"class": "scrolling-multiple-choice"}
                        ),
                    ),
                ),
                (
                    "NETWORK_RPC_URL",
                    forms.JSONField(
                        label=_("RPC URLs for networks"),
                        help_text=_(
                            "JSON field with key=<Network name>_RPC_URL and value = RPC URL"
                        ),
                    ),
                ),
            ]
        )

        return form_fields

    def is_allowed(self, request, **kwargs):
        one_or_more_currencies_configured = len(json.loads(self.settings.TOKEN_RATES)) > 0
        # TODO: Check that TOKEN_RATES conforms to a schema.

        at_least_one_unused_address = (
            WalletAddress.objects.all().unused().for_event(request.event).exists()
        )
        at_least_one_network_configured = all(
            (
                len(json.loads(self.settings._NETWORKS)) > 0,
                # TODO: Check that NETWORK_RPC_URL mappings contain all networks selected
                # TODO: Check that NETWORK_RPC_URL conforms to a schema
                len(self.settings.NETWORK_RPC_URL) > 0,
            )
        )

        return all(
            (
                one_or_more_currencies_configured,
                at_least_one_unused_address,
                at_least_one_network_configured,
                super().is_allowed(request),
            )
        )

    @property
    def payment_form_fields(self):
        currency_type_choices = ()

        rates = json.loads(self.settings.TOKEN_RATES)
        network_ids = set(json.loads(self.settings._NETWORKS))

        for token in registry:
            if token.is_allowed(rates, network_ids):
                currency_type_choices += token.TOKEN_VERBOSE_NAME_TRANSLATED
        
        if len(currency_type_choices) == 0:
            raise ImproperlyConfigured("No currencies configured")

        form_fields = OrderedDict(
            list(super().payment_form_fields.items())
            + [
                (
                    "currency_type",
                    forms.ChoiceField(
                        label=_("Payment currency"),
                        help_text=_("Select the currency you will use for payment."),
                        widget=forms.RadioSelect,
                        choices=currency_type_choices,
                        initial="ETH",
                    ),
                )
            ]
        )

        return form_fields

    def checkout_confirm_render(self, request):
        template = get_template("pretix_eth/checkout_payment_confirm.html")

        return template.render()

    def checkout_prepare(self, request, cart):
        form = self.payment_form(request)

        if form.is_valid():
            # currency_info = "ETH-Ethereum Mainnet" etc.
            request.session["payment_currency_type"] = \
                token_verbose_name_to_token_network_id(form.cleaned_data["currency_type"])
            self._update_session_payment_amount(request, cart["total"])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            # currency_info = "ETH-Ethereum Mainnet" or "DAI-ZkSync" etc.
            request.session["payment_currency_type"] = \
                token_verbose_name_to_token_network_id(form.cleaned_data["currency_type"])
            self._update_session_payment_amount(request, payment.amount)
            return True

        return False

    def payment_is_valid_session(self, request):
        # Note: payment_currency_type check already done in token_verbose_name_to_token_network_id()
        return all(
            (
                "payment_currency_type" in request.session, 
                "payment_time" in request.session,
                "payment_amount" in request.session,
            )
        )

    def _payment_is_valid_info(self, payment: OrderPayment) -> bool:
        # Note: payment_currency_type check already done in token_verbose_name_to_token_network_id()
        return all(
            (
                "currency_type" in payment.info_data,
                "time" in payment.info_data,
                "amount" in payment.info_data,
            )
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment.info_data = {
            "currency_type": request.session["payment_currency_type"],
            "time": request.session["payment_time"],
            "amount": request.session["payment_amount"],
        }
        payment.save(update_fields=["info"])

    def _update_session_payment_amount(self, request: HttpRequest, total):
        token: IToken = \
            all_token_and_network_ids_to_tokens[request.session["payment_currency_type"]]
        final_price = token.get_ticket_price_in_token(
            total, json.loads(self.settings.TOKEN_RATES)
        )

        request.session["payment_amount"] = final_price
        request.session["payment_time"] = int(time.time())

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/pending.html")

        payment_is_valid = self._payment_is_valid_info(payment)
        ctx = {
            "payment_is_valid": payment_is_valid,
            "order": payment.order,
        }

        if not payment_is_valid:
            return template.render(ctx)

        wallet_address = WalletAddress.objects.get_for_order_payment(payment).hex_address
        currency_type = request.session["payment_currency_type"]
        payment_amount = payment.info_data["amount"]
        amount_in_ether_or_token = from_wei(payment_amount, "ether")

        # Get payment instructions based on the network type:
        token: IToken = all_token_and_network_ids_to_tokens[currency_type]
        instructions = token.payment_instructions(
            wallet_address, payment_amount, amount_in_ether_or_token
        )

        ctx.update(instructions)
        ctx["network_name"] = token.NETWORK_VERBOSE_NAME

        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/control.html")

        ctx = {
            "payment_info": payment.info_data,
        }

        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return self.payment_refund_supported(payment)

    def execute_refund(self, refund: OrderRefund):
        if refund.payment is None:
            raise Exception("Invariant: No payment associated with refund")

        wallet_queryset = WalletAddress.objects.filter(order_payment=refund.payment)

        if wallet_queryset.count() != 1:
            raise Exception(
                "Invariant: There is not assigned wallet address to this payment"
            )

        refund.info_data = {
            "currency_type": refund.payment.info_data["currency_type"],
            "amount": refund.payment.info_data["amount"],
            "wallet_address": wallet_queryset.first().hex_address,
        }

        refund.save(update_fields=["info"])
