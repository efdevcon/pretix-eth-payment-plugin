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
from .txn_check import check_txn_confirmation

logger = logging.getLogger(__name__)


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
        d = OrderedDict(
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
        d.move_to_end('ETH', last=True)
        d.move_to_end('DAI', last=True)
        return d

    ##def is_allowed(self, request):
    #    return bool(
    #        (self.settings.DAI or self.settings.ETH) and super().is_allowed(request)
    #    )

    @property
    def payment_form_fields(self):
        e = ('ETH', _('ETH'))
        d = ('DAI', _('DAI'))
        if self.settings.ETH and self.settings.DAI:
            tup = (d, e)
        elif self.settings.DAI:
            tup = (d,)
        elif self.settings.ETH:
            tup = (e,)
        else:
            raise ImproperlyConfigured("Must have one of `ETH` or `DAI` enabled for payments")
        form = OrderedDict(
            list(super().payment_form_fields.items())
            + [
                ('currency_type', forms.ChoiceField(
                    label=_('Select the currency you want to pay in'),
                    widget=forms.Select,
                    choices=tup,
                    initial='ETH'
                )),
            ]
        )
        return form

    def checkout_confirm_render(self, request): 
        template = get_template('pretix_eth/checkout_payment_confirm.html')
        currency = request.session['payment_ethereum_fm_currency']
        ctx = {
            'request': request, 'event': self.event, 'settings': self.settings, 'provider': self,
            'from': self.settings.ETH if (currency == 'ETH') else self.settings.DAI,
            'amount': request.session['payment_ethereum_amount'],
            'currency': currency
        }
        return template.render(ctx)

    def checkout_prepare(self, request, total):
        form = self.payment_form(request)
        if form.is_valid():
          request.session['payment_ethereum_fm_currency'] = form.cleaned_data['currency_type']
          self._get_rates_checkout(request, total['total'])
          return True
        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)
        if form.is_valid():
          request.session['payment_ethereum_fm_currency'] = form.cleaned_data['currency_type']
          self._get_rates(request, payment)
          return True
        return False

    def payment_is_valid_session(self, request):
        return all([
            'payment_ethereum_fm_currency' in request.session,
            'payment_ethereum_time' in request.session,
            'payment_ethereum_amount' in request.session,
       ])

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment.refresh_from_db()
        txn_hash = request.session['payment_ethereum_fm_txn_hash']
        from_address = request.session['payment_ethereum_fm_address']
        currency = request.session['payment_ethereum_fm_currency']
        amount = request.session['payment_ethereum_amount']
        timestamp = request.session['payment_ethereum_time']
        to_address = self.settings.ETH if (currency == 'ETH') else self.settings.DAI
        if check_txn_confirmation(txn_hash, from_address, to_address, currency, amount, timestamp):
            try:
                 payment.confirm()
            except Quota.QuotaExceededException:
                raise PaymentException(str(e))
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
        if (request.session['payment_ethereum_fm_currency'] == 'ETH'):
            cur = self.settings.ETH
        else:
            cur = self.settings.DAI
            ctx = {
                'request': request, 'event': self.event, 'settings': self.settings,
                'payment_info': cur,
                'order': payment.order, 'provname': self.verbose_name,
                'currency': request.session['payment_ethereum_fm_currency'],
                'amount': request.session['payment_ethereum_amount']
            }
        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/control.html')
        ctx = {
            'request': request, 'event': self.event, 'settings': self.settings,
            'order': payment.order,
            'provname': self.verbose_name,
            'currency': request.session['payment_ethereum_fm_currency'],
            'amount': request.session['payment_ethereum_amount']
        }
        r = template.render(ctx)
        r._csp_ignore = True
        return r

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return False

