from collections import OrderedDict

from django import forms

from pretix.base.exporter import ListExporter
from pretix.base.models import (
    OrderPayment,
    OrderRefund,
)
from pretix_eth.models import WalletAddress

import pytz


def date_to_string(time_zone, date):
    return date.astimezone(time_zone).date().strftime('%Y-%m-%d')


def payment_to_row(payment):
    time_zone = pytz.timezone(payment.order.event.settings.timezone)
    if payment.payment_date:
        completion_date = date_to_string(time_zone, payment.payment_date)
    else:
        completion_date = ''

    token = payment.info_data.get("currency_type", "")
    # token = "DAI-L1". Get "DAI" (token_currency_name) so it can be used to get fiat_rate
    token_currency_name = token.split("-")[0].strip()
    fiat_amount = payment.amount
    token_amount = payment.info_data.get("amount", "")

    # Show fiat to token price conversion on exports.
    # get token rates from order.info_data. But default to admin settings (if info not present)
    token_rates = payment.info_data.get("token_rates", {})
    fiat_rate = token_rates.get(
        f"{token_currency_name}_RATE", "Error fetching from order data"
    )

    wallet_address = WalletAddress.objects.filter(order_payment=payment).first()
    hex_wallet_address = wallet_address.hex_address if wallet_address else ""

    row = [
        "Payment",
        payment.order.event.slug,
        payment.order.code,
        payment.full_id,
        date_to_string(time_zone, payment.created),
        completion_date,
        payment.state,
        fiat_amount,
        token_amount,
        token,
        fiat_rate,
        hex_wallet_address,
    ]
    return row


def refund_to_row(refund):
    time_zone = pytz.timezone(refund.order.event.settings.timezone)
    if refund.execution_date:
        completion_date = date_to_string(time_zone, refund.execution_date)
    else:
        completion_date = ''

    token = refund.info_data.get("currency_type", "")
    # token = "DAI-L1". Get "DAI" (token_currency_name) so it can be used to get fiat_rate
    token_currency_name = token.split("-")[0].strip()
    fiat_amount = refund.amount
    token_amount = refund.info_data.get("amount", "")

    # Show fiat to token price conversion on exports.
    # get token rates from refund.info. But default to admin settings (if info not present)
    token_rates = refund.info_data.get("token_rates", {})
    fiat_rate = token_rates.get(
        f"{token_currency_name}_RATE", "Error fetching from order data"
    )

    wallet_address = WalletAddress.objects.filter(order_payment=refund.payment).first()
    hex_wallet_address = wallet_address.hex_address if wallet_address else ""

    row = [
        "Refund",
        refund.order.event.slug,
        refund.order.code,
        refund.full_id,
        date_to_string(time_zone, refund.created),
        completion_date,
        refund.state,
        fiat_amount,
        token_amount,
        token,
        fiat_rate,
        hex_wallet_address,
    ]
    return row


class EthereumOrdersExporter(ListExporter):
    identifier = 'ethorders'
    verbose_name = 'Ethereum orders and refunds'

    headers = (
        'Type', 'Event slug', 'Order', 'Payment ID', 'Creation date',
        'Completion date', 'Status', 'Fiat Amount', 'Token Amount',
        'Token Name', 'Token Rate in Fiat', 'Wallet address'
    )

    @property
    def additional_form_fields(self):
        return OrderedDict(
            [
                ('payment_states',
                 forms.MultipleChoiceField(
                     label='Payment states',
                     choices=OrderPayment.PAYMENT_STATES,
                     initial=[OrderPayment.PAYMENT_STATE_CONFIRMED,
                              OrderPayment.PAYMENT_STATE_REFUNDED],
                     widget=forms.CheckboxSelectMultiple,
                     required=False
                 )),
                ('refund_states',
                 forms.MultipleChoiceField(
                     label='Refund states',
                     choices=OrderRefund.REFUND_STATES,
                     initial=[OrderRefund.REFUND_STATE_DONE, OrderRefund.REFUND_STATE_CREATED,
                              OrderRefund.REFUND_STATE_TRANSIT],
                     widget=forms.CheckboxSelectMultiple,
                     required=False
                 )),
            ]
        )

    def iterate_list(self, form_data):
        payments = OrderPayment.objects.filter(
            order__event__in=self.events,
            state__in=form_data.get('payment_states', []),
            provider='ethereum'
        ).order_by('created')

        refunds = OrderRefund.objects.filter(
            order__event__in=self.events,
            state__in=form_data.get('refund_states', []),
            provider='ethereum'
        ).order_by('created')

        objs = sorted(list(payments) + list(refunds), key=lambda obj: obj.created)

        yield self.headers

        yield self.ProgressSetTotal(total=len(objs))
        for obj in objs:
            if isinstance(obj, OrderPayment):
                row = payment_to_row(obj)
            elif isinstance(obj, OrderRefund):
                row = refund_to_row(obj)
            else:
                raise Exception(
                    'Invariant:Expected OrderPayment or OrderRefund, found {0}'.format((obj))
                )
            yield row

    def get_filename(self):
        if self.is_multievent:
            return '{}_payments'.format(self.events.first().organizer.slug)
        else:
            return '{}_payments'.format(self.event.slug)
