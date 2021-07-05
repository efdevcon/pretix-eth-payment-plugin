import decimal
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

from eth_utils import to_wei, from_wei

from .models import WalletAddress
from .network.networks import (
    all_network_ids_to_networks,
    all_network_verbose_names_to_ids,
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
                    "ETH_RATE",
                    forms.DecimalField(
                        label=_("ETH rate"),
                        help_text=_(
                            "The Ethereum exchange rate in ETH per unit fiat. Leave out if you do not want to accept ETH"
                        ),  # noqa: E501
                        required=False,
                    ),
                ),
                (
                    "DAI_RATE",
                    forms.DecimalField(
                        label=_("DAI rate"),
                        help_text=_(
                            "The DAI exchange rate in DAI per unit fiat. Leave out if you do not want to accept DAI"
                        ),  # noqa: E501
                        required=False,
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
                        ],  # noqa: E501
                        help_text=_(
                            "The networks to be configured for crypto payments"
                        ),
                        widget=forms.CheckboxSelectMultiple(
                            attrs={"class": "scrolling-multiple-choice"}
                        ),
                    ),
                ),
            ]
        )

        form_fields.move_to_end("ETH_RATE", last=True)
        form_fields.move_to_end("DAI_RATE", last=True)

        return form_fields

    def is_allowed(self, request, **kwargs):
        one_or_more_currencies_configured = any(
            (
                self.settings.ETH_RATE,
                self.settings.DAI_RATE,
            )
        )
        at_least_one_unused_address = (
            WalletAddress.objects.all().unused().for_event(request.event).exists()
        )

        return all(
            (
                one_or_more_currencies_configured,
                at_least_one_unused_address,
                super().is_allowed(request),
            )
        )

    @property
    def payment_form_fields(self):
        currency_type_choices = ()
        network_ids_selected = json.loads(self.settings._NETWORKS)

        if self.settings.DAI_RATE:
            for network_id in network_ids_selected:
                currency_type_choices += all_network_ids_to_networks[
                    network_id
                ].dai_currency_choice
        if self.settings.ETH_RATE:
            for network_id in network_ids_selected:
                currency_type_choices += all_network_ids_to_networks[
                    network_id
                ].eth_currency_choice

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
            # currency_info = "ETH-Ethereum Mainnet" or "DAI-ZkSync" etc.
            currency_info = form.cleaned_data["currency_type"].split("-")

            if not currency_info[1] in all_network_verbose_names_to_ids.keys():
                return False
            request.session["payment_currency_type"] = currency_info[0]
            request.session["payment_network"] = all_network_verbose_names_to_ids[
                currency_info[1]
            ]
            self._update_session_payment_amount(request, cart["total"])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            # currency_info = "ETH-Ethereum Mainnet" or "DAI-ZkSync" etc.
            currency_info = form.cleaned_data["currency_type"].split("-")

            if not currency_info[1] in all_network_verbose_names_to_ids.keys():
                return False
            request.session["payment_currency_type"] = currency_info[0]
            request.session["payment_network"] = all_network_verbose_names_to_ids[
                currency_info[1]
            ]
            self._update_session_payment_amount(request, payment.amount)
            return True

        return False

    def payment_is_valid_session(self, request):
        return all(
            (
                "payment_currency_type" in request.session,
                "payment_network" in request.session,
                "payment_time" in request.session,
                "payment_amount" in request.session,
                request.session["payment_network"] 
                in all_network_ids_to_networks.keys(),
            )
        )

    def _payment_is_valid_info(self, payment: OrderPayment) -> bool:
        return all(
            (
                "currency_type" in payment.info_data,
                "time" in payment.info_data,
                "amount" in payment.info_data,
                payment.info_data["currency_type"].split("-")[1]
                in all_network_ids_to_networks.keys(),  # noqa: E501
            )
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        # TODO: For now, payment.currency_type = "ETH-L1" instead of separating the network part.
        currency_type = (
            request.session["payment_currency_type"]
            + "-"
            + request.session["payment_network"]
        )  # noqa: E501
        payment_timestamp = request.session["payment_time"]
        payment_amount = request.session["payment_amount"]

        payment.info_data = {
            "currency_type": currency_type,
            "time": payment_timestamp,
            "amount": payment_amount,
        }
        payment.save(update_fields=["info"])

    def _get_final_price(self, total, currency_type):
        rounding_base = decimal.Decimal("1.00000")

        if currency_type == "ETH":
            chosen_currency_rate = decimal.Decimal(self.settings.ETH_RATE)
        elif currency_type == "DAI":
            chosen_currency_rate = decimal.Decimal(self.settings.DAI_RATE)
        else:
            raise ImproperlyConfigured(f"Unrecognized currency type: {currency_type}")

        rounded_price = (total * chosen_currency_rate).quantize(rounding_base)
        final_price = to_wei(rounded_price, "ether")

        return final_price

    def _update_session_payment_amount(self, request: HttpRequest, total):
        final_price = self._get_final_price(
            total, request.session["payment_currency_type"]
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

        wallet_address = WalletAddress.objects.get_for_order_payment(
            payment
        ).hex_address
        currency_type = request.session["payment_currency_type"]
        payment_amount = payment.info_data["amount"]
        amount_in_ether_or_dai = from_wei(payment_amount, "ether")

        # Get payment instructions based on the network type:
        network_id = request.session["payment_network"]
        network = all_network_ids_to_networks[network_id]
        instructions = network.payment_instructions(
            wallet_address, payment_amount, amount_in_ether_or_dai, currency_type
        )  # noqa: E501

        ctx.update(instructions)
        ctx["network_name"] = network.verbose_name

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
