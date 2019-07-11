import time
from collections import OrderedDict

import json
import logging
import requests
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from requests import Session
from requests.exceptions import ConnectionError

from pretix.base.models import OrderPayment, Quota
from pretix.base.payment import BasePaymentProvider, PaymentException

logger = logging.getLogger(__name__)

ETH_CHOICE = ('ETH', _('Ethereum'))
DAI_CHOICE = ('DAI', _('DAI'))


class Ethereum(BasePaymentProvider):
    identifier = 'ethereum'
    verbose_name = _('Ethereum')
    public_name = _('Ethereum')

    def settings_content_render(self, request):
        if not self.settings.token:
            return (
                "<p>An address where payment will be made.</p>"
            )

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
                ))
            ]
        )

        form_fields.move_to_end('ETH', last=True)
        form_fields.move_to_end('DAI', last=True)

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
                    label=_('Select the currency you want to pay in'),
                    widget=forms.Select,
                    choices=currency_type_choices,
                    initial='ETH'
                )),
                ('txn_hash', forms.CharField(
                    label=_('Transaction hash'),
                    help_text=_('Enter the hash of the transaction in which you paid with the selected currency'),
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
            'txn_hash': request.session['payment_ethereum_fm_txn_hash'],
            'currency': request.session['payment_ethereum_fm_currency'],
        }

        return template.render(ctx)

    def checkout_prepare(self, request, total):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_fm_txn_hash'] = form.cleaned_data['txn_hash']
            request.session['payment_ethereum_fm_currency'] = form.cleaned_data['currency_type']
            self._get_rates_checkout(request, total['total'])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_fm_txn_hash'] = form.cleaned_data['txn_hash']
            request.session['payment_ethereum_fm_currency'] = form.cleaned_data['currency_type']
            self._get_rates(request, payment)
            return True

        return False

    def payment_is_valid_session(self, request):
        return all(
            'payment_ethereum_fm_txn_hash' in request.session,
            'payment_ethereum_fm_currency' in request.session,
            'payment_ethereum_time' in request.session,
            'payment_ethereum_amount' in request.session,
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment.info_data = {
            'txn_hash': request.session['payment_ethereum_fm_txn_hash'],
            'currency': request.session['payment_ethereum_fm_currency'],
            'time': request.session['payment_ethereum_time'],
            'amount': request.session['payment_ethereum_amount'],
        }
        payment.save(update_fields=['info'])

        try:
            if request.session['payment_ethereum_fm_currency'] == 'ETH':
                response = requests.get(
                    f'https://api.ethplorer.io/getAddressTransactions/{self.settings.ETH}?apiKey=freekey'  # noqa: E501
                )
                results = response.json()

                for result in results:
                    if result['success'] == True and result['from'] == request.session['payment_ethereum_fm_address']:  # noqa: E501
                        if result['timestamp'] > request.session['payment_ethereum_time'] and result['value'] >= request.session['payment_ethereum_amount']:  # noqa: E501
                            try:
                                payment.confirm()
                            except Quota.QuotaExceededException as e:
                                raise PaymentException(str(e))
            else:
                response = requests.get(
                    f'https://blockscout.com/poa/dai/api?module=account&action=txlist&address={self.settings.DAI}'  # noqa: E501
                )
                results = response.json()

                for result in results['result']:
                    if result['txreceipt_status'] == '1' and result['from'] == request.session['payment_ethereum_fm_address']:  # noqa: E501
                        #           if (result['timestamp'] > request.session['payment_ethereum_time'] and result[  # noqa: E501
                        # 'value'] >= request.session['payment_ethereum_amount']):
                        try:
                            payment.confirm()
                        except Quota.QuotaExceededException as e:
                            raise PaymentException(str(e))
        except (NameError, TypeError, AttributeError):
            pass

        return None

    def _get_rates_from_api(self, total, currency):
        try:
            if self.event.currency == 'USD':
                rate = requests.get('https://api.bitfinex.com/v1/pubticker/' + currency + 'usd')
                rate = rate.json()
                final_price = float(total) / float(rate['last_price'])
            elif self.event.currency == 'DAI':
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
                final_price = float(total) / float(data['data'][currency]['quote'][self.event.currency]['price'])  # noqa: E501
            else:
                raise ImproperlyConfigured("Unrecognized currency: {0}".format(self.event.currency))

            return round(final_price, 2)
        except ConnectionError:
            logger.exception('Internal eror occured.')
            raise PaymentException(
                _('Please try again and get in touch with us if this problem persists.')
            )

    def _get_rates_checkout(self, request: HttpRequest, total):
        final_price = self._get_rates_from_api(total, request.session['payment_ethereum_fm_currency'])  # noqa: E501

        request.session['payment_ethereum_amount'] = round(final_price, 2)
        request.session['payment_ethereum_time'] = int(time.time())

    def _get_rates(self, request: HttpRequest, payment: OrderPayment):
        final_price = self._get_rates_from_api(payment.amount, request.session['payment_ethereum_fm_currency'])  # noqa: E501

        request.session['payment_ethereum_amount'] = round(final_price, 2)
        request.session['payment_ethereum_time'] = int(time.time())

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/pending.html')

        if request.session['payment_ethereum_fm_currency'] == 'ETH':
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
            'coin': payment.info_data['currency'],
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
            'coin': request.session['payment_ethereum_fm_currency'],
        }

        r = template.render(ctx)
        r._csp_ignore = True

        return r

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return False
