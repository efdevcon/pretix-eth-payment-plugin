import logging
import time
from collections import OrderedDict

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template import RequestContext
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _


from pretix.base.models import (
    OrderPayment,
    OrderRefund,
)
from pretix.base.payment import BasePaymentProvider

from eth_utils import from_wei

#from .models import WalletAddress
from .network.tokens import (
    IToken,
    registry,
    all_network_verbose_names_to_ids,
    all_token_and_network_ids_to_tokens,
    token_verbose_name_to_token_network_id,
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
    test_mode_message = "Paying in Test Mode"

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
                            "JSON field with key = {TOKEN_SYMBOL}_RATE and value = amount for a token in the fiat currency you have chosen. E.g. 'ETH_RATE':4000 means 1 ETH = 4000 in the fiat currency."  # noqa: E501
                        ),
                    ),
                ),
                # Based on pretix source code, MultipleChoiceField breaks if settings doesnt start with an "_". No idea how this works... # noqa: E501
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
                    "SINGLE_RECEIVER_ADDRESS",
                    forms.CharField(
                        label=_("Payment receiver address."),
                        help_text=_("Caution: Must work on all networks configured.")
                    )
                ),
                (
                    "NETWORK_RPC_URL",
                    forms.JSONField(
                        label=_("RPC URLs for networks"),
                        help_text=_(
                            "JSON field with key = {NETWORK_IDENTIFIER}_RPC_URL and value = url of the network RPC endpoint you are using"  # noqa: E501
                        ),
                    ),
                ),
            ]
        )

        form_fields["_NETWORKS"]._as_type = list
        return form_fields

    def get_token_rates_from_admin_settings(self):
        return self.settings.get("TOKEN_RATES", as_type=dict, default={})

    def get_networks_chosen_from_admin_settings(self):
        return set(self.settings.get("_NETWORKS", as_type=list, default=[]))

    def get_receiving_address(self):
        return self.settings.SINGLE_RECEIVER_ADDRESS

    def is_allowed(self, request, **kwargs):
        one_or_more_currencies_configured = (
            len(self.get_token_rates_from_admin_settings()) > 0
        )
        # TODO: Check that TOKEN_RATES conforms to a schema.
        if not one_or_more_currencies_configured:
            logger.error("No currencies configured")

        at_least_one_network_configured = all(
            (
                len(self.get_networks_chosen_from_admin_settings()) > 0,
                # TODO: Check that NETWORK_RPC_URL mappings contain all networks selected
                # TODO: Check that NETWORK_RPC_URL conforms to a schema
                len(self.settings.NETWORK_RPC_URL) > 0,
            )
        )
        if not at_least_one_network_configured:
            logger.error("No networks configured")

        receiving_address = self.get_receiving_address()
        single_receiver_mode_configured = len(receiving_address) > 0

        if not single_receiver_mode_configured:
            logger.error("Single receiver addresses not configured properly")

        return all(
            (
                one_or_more_currencies_configured,
                at_least_one_network_configured,
                single_receiver_mode_configured,
                super().is_allowed(request),
            )
        )

    @property
    def payment_form_fields(self):
        currency_type_choices = ()

        rates = self.get_token_rates_from_admin_settings()
        network_ids = self.get_networks_chosen_from_admin_settings()

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
            # currency_type = "<token_symbol> - <network verbose name>" etc.
            # But request.session would store "<token_symbol> - <network id>"
            request.session[
                "payment_currency_type"
            ] = token_verbose_name_to_token_network_id(
                form.cleaned_data["currency_type"]
            )
            self._update_session_payment_amount(request, cart["total"])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            # currency_type = "<token_symbol> - <network verbose name>" etc.
            # But request.session would store "<token_symbol> - <network id>"
            request.session[
                "payment_currency_type"
            ] = token_verbose_name_to_token_network_id(
                form.cleaned_data["currency_type"]
            )
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
        token: IToken = all_token_and_network_ids_to_tokens[
            request.session["payment_currency_type"]
        ]
        final_price = token.get_ticket_price_in_token(
            total, self.get_token_rates_from_admin_settings()
        )

        request.session["payment_amount"] = final_price
        request.session["payment_time"] = int(time.time())

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/pending.html")

        payment_is_valid = self._payment_is_valid_info(payment)
        ctx = RequestContext(request, {
            "payment_is_valid": payment_is_valid,
            "order": payment.order,
            "payment": payment,
        })

        if not payment_is_valid:
            return template.render(ctx)

        # todo move to a util method?
        wallet_address = self.get_receiving_address()
        currency_type = payment.info_data["currency_type"]
        payment_amount = payment.info_data["amount"]
        amount_in_ether_or_token = from_wei(payment_amount, "ether")

        # Get payment instructions based on the network type:
        token: IToken = all_token_and_network_ids_to_tokens[currency_type]
        instructions = token.payment_instructions(
            wallet_address, payment_amount, amount_in_ether_or_token
        )

        ctx.update(instructions)
        ctx["network_name"] = token.NETWORK_VERBOSE_NAME
        ctx["chain_id"] = token.CHAIN_ID
        ctx["token_symbol"] = token.TOKEN_SYMBOL
        ctx["transaction_details_url"] = payment.pk

        return template.render(ctx.flatten())

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/control.html")

        hex_wallet_address = self.get_receiving_address()

        ctx = {"payment_info": payment.info_data, "wallet_address": hex_wallet_address}

        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return self.payment_refund_supported(payment)

    def execute_refund(self, refund: OrderRefund):
        if refund.payment is None:
            raise Exception("Invariant: No payment associated with refund")

        wallet_queryset = None  # todo WalletAddress.objects.filter(order_payment=refund.payment)

        #todo fix
        # if wallet_queryset.count() != 1:
        #     raise Exception(
        #         "Invariant: There is not assigned wallet address to this payment"
        #     )
        # refund.info_data = {
        #     "currency_type": refund.payment.info_data["currency_type"],
        #     "amount": refund.payment.info_data["amount"],
        #     "wallet_address": wallet_queryset.first().hex_address,
        # }

        refund.save(update_fields=["info"])
