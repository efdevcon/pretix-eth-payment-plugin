import time
from collections import OrderedDict

import json
import logging
import requests
from django import forms
from django.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from requests import Session
from requests.exceptions import ConnectionError

from pretix.base.models import OrderPayment, Quota
from pretix.base.payment import BasePaymentProvider, PaymentException

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
        d = OrderedDict(list(super().settings_form_fields.items()) +
                        [
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

    def is_allowed(self, request, total):
        return self.settings.DAI or self.settings.ETH and super().is_allowed(request, total)

    @property
    def payment_form_fields(self):
        e = ('ETH', _('Ethereum'))
        d = ('DAI', _('DAI'))
        if self.settings.ETH and self.settings.DAI:
            tup = (e, d)
        elif self.settings.DAI:
            tup = (d,)
        elif self.settings.ETH:
            tup = (e,)
        else:
            raise ImproperlyConfigured("Must have one of `ETH` or `DAI` enabled for payments")
        form = OrderedDict(list(super().payment_form_fields.items()) + [
            ('currency_type', forms.ChoiceField(
                label=_('Select the currency you want to pay in'),
                widget=forms.Select,
                choices=tup,
                initial='ETH'
            )),
            ('address', forms.CharField(
                label=_('Wallet address'),
                help_text=_('Enter the wallet address you will deposit from here.'),
                required=True,
            )),
        ]
                           )
        return form

    def checkout_confirm_render(self, request):
        template = get_template('pretix_eth/checkout_payment_confirm.html')
        ctx = {'request': request, 'event': self.event, 'settings': self.settings, 'provider': self,
               'from': request.session['payment_ethereum_fm_address'],
               'currency': request.session['payment_ethereum_fm_currency']}
        return template.render(ctx)

    def checkout_prepare(self, request, total):
        form = self.payment_form(request)
        if form.is_valid():
            request.session['payment_ethereum_fm_address'] = form.cleaned_data['address']
            request.session['payment_ethereum_fm_currency'] = form.cleaned_data['currency_type']
            self._get_rates_checkout(request, total['total'])
            return True
        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)
        if form.is_valid():
            request.session['payment_ethereum_fm_address'] = form.cleaned_data['address']
            request.session['payment_ethereum_fm_currency'] = form.cleaned_data['currency_type']
            self._get_rates(request, payment)
            return True
        return False

    def payment_is_valid_session(self, request):
        return (
                'payment_ethereum_fm_address' in request.session and
                'payment_ethereum_fm_currency' in request.session and
                'payment_ethereum_time' in request.session and
                'payment_ethereum_amount' in request.session
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment.info_data = {
            'sender_address': request.session['payment_ethereum_fm_address'],
            'currency': request.session['payment_ethereum_fm_currency'],
            'time': request.session['payment_ethereum_time'],
            'amount': request.session['payment_ethereum_amount'],
        }
        payment.save(update_fields=['info'])
        try:
            if request.session['payment_ethereum_fm_currency'] == 'ETH':
                dec = requests.get(
                    'https://api.ethplorer.io/getAddressTransactions/' + self.settings.ETH + '?apiKey=freekey')
                deca = dec.json()
                if len(deca) > 0:
                    for decc in deca:
                        if decc['success'] == True and decc['from'] == request.session['payment_ethereum_fm_address']:
                            if decc['timestamp'] > request.session['payment_ethereum_time'] and decc['value'] >= \
                                    request.session['payment_ethereum_amount']:
                                try:
                                    payment.confirm()
                                except Quota.QuotaExceededException as e:
                                    raise PaymentException(str(e))
            else:
                dec = requests.get(
                    'https://blockscout.com/poa/dai/api?module=account&action=txlist&address=' + self.settings.DAI)
                deca = dec.json()
                for decc in deca['result']:
                    if decc['txreceipt_status'] == '1' and decc['from'] == request.session[
                        'payment_ethereum_fm_address']:
                        #           if (decc['timestamp'] > request.session['payment_ethereum_time'] and decc[
                        # 'value'] >= request.session['payment_ethereum_amount']):
                        try:
                            payment.confirm()
                        except Quota.QuotaExceededException as e:
                            raise PaymentException(str(e))
        except NameError:
            pass
        except TypeError:
            pass
        except AttributeError:
            pass
        return None

    def _get_rates_from_api(self, total, currency):
        try:
            if self.event.currency == 'USD':
                rate = requests.get('https://api.bitfinex.com/v1/pubticker/' + currency + 'usd')
                rate = rate.json()
                final_price = float(total) / float(rate['last_price'])
            else:
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
                final_price = float(total) / float(data['data'][currency]['quote'][self.event.currency]['price'])
            return round(final_price, 2)
        except ConnectionError as e:
            logger.exception('Internal eror occured.')
            raise PaymentException(_('Please try again and get in touch '
                                     'with us if this problem persists.'))

    def _get_rates_checkout(self, request: HttpRequest, total):
        final_price = self._get_rates_from_api(total, request.session['payment_ethereum_fm_currency'])
        request.session['payment_ethereum_amount'] = round(final_price, 2)
        request.session['payment_ethereum_time'] = int(time.time())

    def _get_rates(self, request: HttpRequest, payment: OrderPayment):
        final_price = self._get_rates_from_api(payment.amount, request.session['payment_ethereum_fm_currency'])
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
            'coin': payment.info_data['currency'],
            'amount': payment.info_data['amount']
        }
        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/control.html')
        ctx = {'request': request, 'event': self.event, 'settings': self.settings,
               'payment_info': payment.info_data, 'order': payment.order, 'provname': self.verbose_name,
               'coin': request.session['payment_ethereum_fm_currency']}
        r = template.render(ctx)
        r._csp_ignore = True
        return r

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return False
