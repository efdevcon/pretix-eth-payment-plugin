from collections import OrderedDict

from django import forms

from pretix.base.exporter import ListExporter
from pretix.base.models import (
    OrderPayment,
    OrderRefund,
)

from web3 import Web3

from pretix_eth.models import SignedMessage

import pytz


def date_to_string(time_zone, date):
    return date.astimezone(time_zone).date().strftime('%Y-%m-%d')


def payment_to_row(payment):
    time_zone = pytz.timezone(payment.order.event.settings.timezone)
    if payment.payment_date:
        completion_date = date_to_string(time_zone, payment.payment_date)
    else:
        completion_date = ''

    currency_type = payment.info_data.get("currency_type", "")

    fiat_amount = payment.amount
    token_amount = payment.info_data.get("amount", "")
    token_rate = payment.info_data.get("token_rate", "")

    confirmed_transaction: SignedMessage = payment.signed_messages.filter(
        is_confirmed=True).first()
    if confirmed_transaction is None:
        confirmed_transaction: SignedMessage = payment.signed_messages.last()

    if confirmed_transaction is not None:
        sender_address = confirmed_transaction.sender_address
        recipient_address = confirmed_transaction.recipient_address
        transaction_hash = confirmed_transaction.transaction_hash
    else:
        sender_address = None
        recipient_address = None
        transaction_hash = None

    row = [
        "Payment",
        payment.order.event.slug,
        payment.order.code,
        payment.full_id,
        date_to_string(time_zone, payment.created),
        completion_date,
        payment.state,
        fiat_amount,
        Web3.from_wei(int(token_amount), 'ether'),
        currency_type,
        sender_address,
        recipient_address,
        transaction_hash,
        token_rate,
    ]

    return row


class EthereumOrdersExporter(ListExporter):
    identifier = 'ethorders'
    verbose_name = 'Ethereum orders and refunds'

    headers = (
        'Type', 'Event slug', 'Order', 'Payment ID', 'Creation date',
        'Completion date', 'Status', 'Fiat Amount', 'Token Amount', 'Token',
        'ETH or DAI sender address', 'ETH or DAI receiver address',
        'Transaction Hash', 'Chain ID', 'DAI contract address',
        'Token Rate at time of order',
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

        yield self.headers

        yield self.ProgressSetTotal(total=payments.count())
        for obj in payments:
            if isinstance(obj, OrderPayment):
                row = payment_to_row(obj)
            else:
                raise Exception(
                    'Invariant:Expected OrderPayment, found {0}'.format((obj))
                )
            yield row

    def get_filename(self):
        if self.is_multievent:
            return '{}_payments'.format(self.events.first().organizer.slug)
        else:
            return '{}_payments'.format(self.event.slug)
