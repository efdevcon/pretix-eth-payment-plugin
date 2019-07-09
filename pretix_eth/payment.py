import hashlib
import json
import logging
import urllib
import time
from collections import OrderedDict

from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

import requests
from django import forms
from django.core import signing
from django.http import HttpRequest
from django.template.loader import get_template
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from typing import Union

from pretix.base.models import OrderPayment, OrderRefund
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.multidomain.urlreverse import build_absolute_uri
from .models import ReferencedEthereumObject
logger = logging.getLogger(__name__)


class Ethereum(BasePaymentProvider):
    identifier = 'ethereum'
    verbose_name = _('Ethereum Plugin')
    public_name = _('Ethereum Plugin')

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
                     help_text=_('Leave empty if you do not want to accept ETH.'),
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
    
 #   def payment_form_render(self, request) -> str:
  #      form = self.payment_form(request)
        #template = get_template('pretix_eth/checkout_payment_form.html')
        #ctx = {'request': request, 'event': self.event, 'settings': self.settings, 'form': form}
        #return template.render(ctx)
   #     return form



    @property
    def payment_form_fields(self):
        e = ('ETH', _('ETH'))
        d = ('DAI', _('DAI'))
        if len(self.settings.ETH) > 0 and len(self.settings.DAI) > 0:
            tup = (e, d)
            pass
        elif len(self.settings.DAI) > 0:
            tup = (d)
            pass
        elif  len(self.settings.ETH) > 0:
            tup = (e)
            pass
        form = OrderedDict(list(super().payment_form_fields.items()) +
         [
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
        ctx = {'request': request, 'event': self.event, 'settings': self.settings, 'provider': self, 'currency': request.session['fm_currency'] }
        return template.render(ctx)

    def checkout_prepare(self, request, total):
        form = self.payment_form(request)
        if form.is_valid():
          request.session['fm_currency'] = form.cleaned_data['currency_type']
          self.exe_checkout(request, total['total'])
          return True
        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)
        if form.is_valid():
          request.session['fm_currency'] = form.cleaned_data['currency_type']
          self.exe(request, payment)
          return True
        return False

    def payment_is_valid_session(self, request):
        return True

    # TODO: how is this checked periodically
    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment.refresh_from_db()
        try:
            if (request.session['fm_currency'] == 'ETH'):
                 dec = requests.get('https://api.ethplorer.io/getAddressTransactions/' + self.settings.ETH + '?apiKey=freekey')
                 deca = dec.json()
                 if len(deca) > 0:
                    for decc in deca:
                        if (decc['success'] == True and decc['from'] == request.session['fm_address']):
                            if (decc['timestamp'] > request.session['time'] and decc['value'] >= request.session['amount']):
                                try:
                                     payment.confirm()
                                except Quota.QuotaExceededException:
                                    raise PaymentException(str(e))
            else:
                # TODO: payment should not be xDai
                dec = requests.get('https://blockscout.com/poa/dai/api?module=account&action=txlist&address=' + self.settings.DAI)
                deca = dec.json()
                for decc in deca['result']:
                    if (decc['txreceipt_status'] == '1' and decc['from'] == request.session['fm_address']):
                 #           if (decc['timestamp'] > request.session['time'] and decc['value'] >= request.session['amount']):
                        try:
                             payment.confirm()
                        except Quota.QuotaExceededException:
                            raise PaymentException(str(e))
        except NameError:
            pass
        except TypeError:
            pass
        except AttributeError:
            pass
        return None

    def exe_checkout(self, request: HttpRequest, payment):
        try:
            rate = requests.get('https://api.bitfinex.com/v1/pubticker/' + request.session['fm_currency'] + 'usd')
            rate = rate.json()
            final_price =  float(payment) / float(rate['last_price'])
            if self.event.currency != 'USD':
                url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
                parameters = {
                  'symbol': request.session['fm_currency'],
                  'convert': self.event.currency,
                  }
                headers = {
                  'Accepts': 'application/json',
                  'X-CMC_PRO_API_KEY': '7578555c-bf3e-4639-8651-11a20ddb30c6',
                  }
                session = Session()
                session.headers.update(headers)

                try:
                  response = session.get(url, params=parameters)
                  data = json.loads(response.text)
                  final_price = float(payment) / float(data['data'][request.session['fm_currency']]['quote'][self.event.currency]['price'])
                except (ConnectionError, Timeout, TooManyRedirects) as e:
                  pass
            request.session['amount'] = str(final_price)
            request.session['time'] = int(time.time())
        except (ConnectionError) as e:
            pass
        return 

    def exe(self, request: HttpRequest, payment: OrderPayment):
        request.session['payment_eth_order_secret'] = payment.order.secret
        try:
            rate = requests.get('https://api.bitfinex.com/v1/pubticker/' + request.session['fm_currency'] + 'usd')
            rate = rate.json()
            final_price =  float(payment.amount) / float(rate['last_price'])
            if self.event.currency != 'USD':
                url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
                parameters = {
                  'symbol': request.session['fm_currency'],
                  'convert': self.event.currency,
                  }
                headers = {
                  'Accepts': 'application/json',
                  'X-CMC_PRO_API_KEY': '7578555c-bf3e-4639-8651-11a20ddb30c6',
                  }
                session = Session()
                session.headers.update(headers)

                try:
                  response = session.get(url, params=parameters)
                  data = json.loads(response.text)
                  final_price = float(payment.amount) / float(data['data'][request.session['fm_currency']]['quote'][self.event.currency]['price'])
                except (ConnectionError, Timeout, TooManyRedirects) as e:
                  pass
            request.session['amount'] = str(final_price)
            request.session['time'] = int(time.time())
        except (ConnectionError) as e:
            logger.exception('Internal eror occured.')
            raise PaymentException(_('Please try again and get in touch '
                                     'with us if this problem persists.'))
        ReferencedEthereumObject.objects.get_or_create(order=payment.order, payment=payment, reference=request.session['time'])
        return

    def redirect(self, request, url):
        if request.session.get('iframe_session', False):
            signer = signing.Signer(salt='safe-redirect')
            return (
                build_absolute_uri(request.event, 'plugins:pretix_eth:redirect') + '?url=' +
                urllib.parse.quote(signer.sign(url))
            )
        else:
            return str(url)


    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/pending.html')
        if (request.session['fm_currency'] == 'ETH'):
            cur = self.settings.ETH
        else:
            cur = self.settings.DAI
        ctx = {'request': request, 'event': self.event, 'settings': self.settings,
                'payment_info' : cur, 'order': payment.order, 'provname': self.verbose_name, 'coin': request.session['fm_currency'], 'amount': request.session['amount']}
        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/control.html')
        ctx = {'request': request, 'event': self.event, 'settings': self.settings,
               'payment_info': payment.info_data, 'order': payment.order, 'provname': self.verbose_name, 'coin': request.session['fm_currency']}
        r = template.render(ctx)
        r._csp_ignore = True
        return r

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return False

    def shred_payment_info(self, obj: Union[OrderPayment, OrderRefund]):
        d = obj.info_data
        for k, v in list(d.items()):
            if v not in ('id', 'status', 'price', 'currency', 'invoiceTime', 'paymentSubtotals',
                         'paymentTotals', 'transactionCurrency', 'amountPaid'):
                d[k] = '█'
        obj.info_data = d
        obj.save()

        for le in obj.order.all_logentries().filter(action_type="pretix_ethereum.event").exclude(data=""):
            d = le.parsed_data
            if 'data' in d:
                for k, v in list(d['data'].items()):
                    if v not in ('id', 'status', 'price', 'currency', 'invoiceTime', 'paymentSubtotals',
                                 'paymentTotals', 'transactionCurrency', 'amountPaid'):
                        d['data'][k] = '█'
                le.data = json.dumps(d)
                le.shredded = True
                le.save(update_fields=['data', 'shredded'])

