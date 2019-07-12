import decimal
import json
import logging
import time
from collections import OrderedDict

import requests
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from eth_utils import import_string
from requests import Session
from requests.exceptions import ConnectionError

from pretix.base.models import OrderPayment, Quota
from pretix.base.payment import BasePaymentProvider, PaymentException

from eth_utils import to_wei, from_wei

from .providers import (
    TransactionProviderAPI,
    TokenProviderAPI,
)

logger = logging.getLogger(__name__)

ETH_CHOICE = ('ETH', _('ETH'))
DAI_CHOICE = ('DAI', _('DAI'))

DEFAULT_TRANSACTION_PROVIDER = 'pretix_eth.providers.BlockscoutTransactionProvider'
DEFAULT_TOKEN_PROVIDER = 'pretix_eth.providers.BlockscoutTokenProvider'


class Ethereum(BasePaymentProvider):
    identifier = 'ethereum'
    verbose_name = _('Ethereum')
    public_name = _('Ethereum')

    @cached_property
    def transaction_provider(self) -> TransactionProviderAPI:
        transaction_provider_class = import_string(self.settings.get(
            'TRANSACTION_PROVIDER',
            'pretix_eth.providers.BlockscoutTransactionProvider',
        ))
        return transaction_provider_class()

    @cached_property
    def token_provider(self) -> TokenProviderAPI:
        token_provider_class = import_string(self.settings.get(
            'TOKEN_PROVIDER',
            'pretix_eth.providers.BlockscoutTokenProvider',
        ))
        return token_provider_class()

    @property
    def settings_form_fields(self):
        form_fields = OrderedDict(
            list(super().settings_form_fields.items())
            + [
                ('ETH', forms.CharField(
                    label=_('Ethereum wallet address'),
                    help_text=_('Leave empty if you do not want to accept ethereum.'),
                    required=False
                )),
                ('DAI', forms.CharField(
                    label=_('DAI wallet address'),
                    help_text=_('Leave empty if you do not want to accept DAI.'),
                    required=False
                )),
                ('TRANSACTION_PROVIDER', forms.CharField(
                    label=_('Transaction Provider'),
                    help_text=_(
                        f'This determines how the application looks up '
                        f'transfers of Ether.  Leave empty to use the default '
                        f'provider: {DEFAULT_TRANSACTION_PROVIDER}'
                    ),
                    required=False
                )),
                ('TOKEN_PROVIDER', forms.CharField(
                    label=_('Token Provider'),
                    help_text=_(
                        f'This determines how the application looks up token '
                        f'transfers.  Leave empty to use the default provider: '
                        f'{DEFAULT_TOKEN_PROVIDER}'
                    ),
                    required=False
                )),
            ]
        )

        form_fields.move_to_end('ETH', last=True)
        form_fields.move_to_end('DAI', last=True)
        form_fields.move_to_end('TRANSACTION_PROVIDER', last=True)
        form_fields.move_to_end('TOKEN_PROVIDER', last=True)

        return form_fields

    def is_allowed(self, request, **kwargs):
        return bool(
            (self.settings.DAI or self.settings.ETH) and super().is_allowed(request)
        )

    @property
    def payment_form_fields(self):
        if self.settings.ETH and self.settings.DAI:
            currency_type_choices = (DAI_CHOICE, ETH_CHOICE)
        elif self.settings.DAI:
            currency_type_choices = (DAI_CHOICE,)
        elif self.settings.ETH:
            currency_type_choices = (ETH_CHOICE,)
        else:
            raise ImproperlyConfigured("Must have one of `ETH` or `DAI` enabled for payments")

        form_fields = OrderedDict(
            list(super().payment_form_fields.items())
            + [
                ('currency_type', forms.ChoiceField(
                    label=_('Payment currency'),
                    help_text=_('Select the currency you used for payment.'),
                    widget=forms.Select,
                    choices=currency_type_choices,
                    initial='ETH'
                )),
                ('txn_hash', forms.CharField(
                    label=_('Transaction hash'),
                    help_text=_('Enter the hash of the transaction in which you paid with the selected currency.'),  # noqa: E501
                    required=True,
                )),
            ]
        )

        return form_fields

    def checkout_confirm_render(self, request):
        template = get_template('pretix_eth/checkout_payment_confirm.html')

        ctx = {
            'request': request,
            'event': self.event,
            'settings': self.settings,
            'provider': self,
            'txn_hash': request.session['payment_ethereum_txn_hash'],
            'currency_type': request.session['payment_ethereum_currency_type'],
        }

        return template.render(ctx)

    def checkout_prepare(self, request, total):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_txn_hash'] = form.cleaned_data['txn_hash']
            request.session['payment_ethereum_currency_type'] = form.cleaned_data['currency_type']  # noqa: E501
            self._get_rates_checkout(request, total['total'])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_txn_hash'] = form.cleaned_data['txn_hash']
            request.session['payment_ethereum_currency_type'] = form.cleaned_data['currency_type']  # noqa: E501
            self._get_rates(request, payment)
            return True

        return False

    def payment_is_valid_session(self, request):
        return all((
            'payment_ethereum_txn_hash' in request.session,
            'payment_ethereum_currency_type' in request.session,
            'payment_ethereum_time' in request.session,
            'payment_ethereum_amount' in request.session,
        ))

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        txn_hash = request.session['payment_ethereum_txn_hash']
        currency_type = request.session['payment_ethereum_currency_type']
        payment_timestamp = request.session['payment_ethereum_time']
        payment_amount = request.session['payment_ethereum_amount']

        payment.info_data = {
            'txn_hash': txn_hash,
            'currency_type': currency_type,
            'time': payment_timestamp,
            'amount': payment_amount,
        }
        payment.save(update_fields=['info'])

        if currency_type == 'ETH':
            transaction = self.transaction_provider.get_transaction(txn_hash)
            is_valid_payment_transaction = all((
                transaction.success,
                transaction.to == self.settings.ETH,
                transaction.value >= payment_amount,
                transaction.timestamp >= payment_timestamp,
            ))
            if is_valid_payment_transaction:
                try:
                    payment.confirm()
                except Quota.QuotaExceededException as e:
                    raise PaymentException(str(e))
        elif currency_type == 'DAI':
            transfer = self.token_provider.get_ERC20_transfer(txn_hash)
            is_valid_payment_transfer = all((
                transfer.success,
                transfer.to == self.settings.DAI,
                transfer.value >= payment_amount,
                transfer.timestamp >= payment_timestamp,
            ))
            if is_valid_payment_transfer:
                try:
                    payment.confirm()
                except Quota.QuotaExceededException as e:
                    raise PaymentException(str(e))
        else:
            # unkown currency
            raise ImproperlyConfigured(f"Unknown currency: {currency_type}")

    def _get_rates_from_api(self, total, currency):
        try:
            if currency == 'ETH':
                rate = requests.get(f'https://api.bitfinex.com/v1/pubticker/eth{self.event.currency}')  # noqa: E501
                rate = rate.json()
                final_price = to_wei((
                    total / decimal.Decimal(rate['last_price'])
                ).quantize(decimal.Decimal('1.00000')), 'ether')
            elif currency == 'DAI':
                url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
                parameters = {
                    'symbol': currency,
                    'convert': self.event.currency,
                }
                headers = {
                    'Accepts': 'application/json',
                    'X-CMC_PRO_API_KEY': '7578555c-bf3e-4639-8651-11a20ddb30c6',
                }
                session = Session()
                session.headers.update(headers)

                response = session.get(url, params=parameters)
                data = json.loads(response.text)
                final_price = (
                    total / decimal.Decimal(data['data'][currency]['quote'][self.event.currency]['price'])  # noqa: E501
                ).quantize(decimal.Decimal('1.00'))
            else:
                raise ImproperlyConfigured("Unrecognized currency: {0}".format(self.event.currency))

            return round(final_price, 2)
        except ConnectionError:
            logger.exception('Internal eror occured.')
            raise PaymentException(
                _('Please try again and get in touch with us if this problem persists.')
            )

    def _get_rates_checkout(self, request: HttpRequest, total):
        final_price = self._get_rates_from_api(total, request.session['payment_ethereum_currency_type'])  # noqa: E501

        request.session['payment_ethereum_amount'] = final_price
        request.session['payment_ethereum_time'] = int(time.time())

    def _get_rates(self, request: HttpRequest, payment: OrderPayment):
        final_price = self._get_rates_from_api(payment.amount, request.session['payment_ethereum_currency_type'])  # noqa: E501

        request.session['payment_ethereum_amount'] = final_price
        request.session['payment_ethereum_time'] = int(time.time())

    def payment_form_render(self, request: HttpRequest, total: decimal.Decimal):
        # this ensures that the form will pre-populate the transaction hash into the form.
        if 'txhash' in request.GET:
            request.session['payment_ethereum_txn_hash'] = request.GET.get('txhash')
        if 'currency' in request.GET:
            request.session['payment_ethereum_currency_type'] = request.GET.get('currency')
        form = self.payment_form(request)
        template = get_template('pretix_eth/checkout_payment_form.html')
        ctx = {
            'request': request,
            'form': form,
            'ETH_per_ticket': from_wei(self._get_rates_from_api(total, 'ETH'), 'ether'),
            'DAI_per_ticket': self._get_rates_from_api(total, 'DAI'),
            'ETH_address': self.settings.get('ETH'),
            'DAI_address': self.settings.get('DAI'),
        }
        return template.render(ctx)

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/pending.html')

        if request.session['payment_ethereum_currency_type'] == 'ETH':
            cur = self.settings.ETH
        else:
            cur = self.settings.DAI

        ctx = {
            'request': request,
            'event': self.event,
            'settings': self.settings,
            'payment_info': cur,
            'order': payment.order,
            'provname': self.verbose_name,
            'coin': payment.info_data['currency_type'],
            'amount': payment.info_data['amount'],
        }

        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/control.html')

        ctx = {
            'request': request,
            'event': self.event,
            'settings': self.settings,
            'payment_info': payment.info_data,
            'order': payment.order,
            'provname': self.verbose_name,
        }

        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return False
