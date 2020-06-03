import decimal
import logging
import time
from collections import OrderedDict

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from pretix.base.models import OrderPayment
from pretix.base.payment import BasePaymentProvider

from eth_utils import to_wei, from_wei

from .models import WalletAddress

logger = logging.getLogger(__name__)

DEFAULT_TRANSACTION_PROVIDER = 'pretix_eth.providers.BlockscoutMainnetProvider'

RESERVED_ORDER_DIGITS = 5

DAI_MAINNET_ADDRESS = '0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'


def truncate_wei_value(value: int, digits: int) -> int:
    multiplier = 10 ** digits
    return int(round(value / multiplier) * multiplier)


class Ethereum(BasePaymentProvider):
    identifier = 'ethereum'
    verbose_name = _('ETH or DAI')
    public_name = _('ETH or DAI')

    @property
    def settings_form_fields(self):
        form_fields = OrderedDict(
            list(super().settings_form_fields.items()) + [
                ('ETH_RATE', forms.DecimalField(
                    label=_('Ethereum rate'),
                    help_text=_('The Ethereum exchange rate in ETH per unit fiat. Leave out if you do not want to accept ETH'),  # noqa: E501
                    required=False
                )),
                ('DAI_RATE', forms.DecimalField(
                    label=_('DAI rate'),
                    help_text=_('The DAI exchange rate in DAI per unit fiat. Leave out if you do not want to accept DAI'),  # noqa: E501
                    required=False
                )),
            ]
        )

        form_fields.move_to_end('ETH_RATE', last=True)
        form_fields.move_to_end('DAI_RATE', last=True)

        return form_fields

    def is_allowed(self, request, **kwargs):
        one_or_more_currencies_configured = any((
            self.settings.ETH_RATE,
            self.settings.DAI_RATE,
        ))
        at_least_one_unused_address = (
            WalletAddress.objects.all().unused().for_event(request.event).exists()
        )

        return all((
            one_or_more_currencies_configured,
            at_least_one_unused_address,
            super().is_allowed(request),
        ))

    @property
    def payment_form_fields(self):
        currency_type_choices = ()

        if self.settings.DAI_RATE:
            currency_type_choices += (('DAI', _('DAI')),)
        if self.settings.ETH_RATE:
            currency_type_choices += (('ETH', _('ETH')),)

        if len(currency_type_choices) == 0:
            raise ImproperlyConfigured('No currencies configured')

        form_fields = OrderedDict(
            list(super().payment_form_fields.items()) + [
                ('currency_type', forms.ChoiceField(
                    label=_('Payment currency'),
                    help_text=_('Select the currency you will use for payment.'),
                    widget=forms.Select,
                    choices=currency_type_choices,
                    initial='ETH'
                ))
            ]
        )

        return form_fields

    def checkout_confirm_render(self, request):
        template = get_template('pretix_eth/checkout_payment_confirm.html')

        return template.render()

    def checkout_prepare(self, request, cart):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_currency_type'] = form.cleaned_data['currency_type']  # noqa: E501
            self._update_session_payment_amount(request, cart['total'])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_currency_type'] = form.cleaned_data['currency_type']  # noqa: E501
            self._update_session_payment_amount(request, payment.amount)
            return True

        return False

    def payment_is_valid_session(self, request):
        return all((
            'payment_ethereum_currency_type' in request.session,
            'payment_ethereum_time' in request.session,
            'payment_ethereum_amount' in request.session,
        ))

    def _payment_is_valid_info(self, payment: OrderPayment) -> bool:
        return all((
            'currency_type' in payment.info_data,
            'time' in payment.info_data,
            'amount' in payment.info_data,
        ))

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        currency_type = request.session['payment_ethereum_currency_type']
        payment_timestamp = request.session['payment_ethereum_time']

        payment_amount = request.session['payment_ethereum_amount']

        payment.info_data = {
            'currency_type': currency_type,
            'time': payment_timestamp,
            'amount': payment_amount,
        }
        payment.save(update_fields=['info'])

    def _get_final_price(self, total, currency_type):
        rounding_base = decimal.Decimal('1.00000')

        if currency_type == 'ETH':
            chosen_currency_rate = decimal.Decimal(self.settings.ETH_RATE)
        elif currency_type == 'DAI':
            chosen_currency_rate = decimal.Decimal(self.settings.DAI_RATE)
        else:
            raise ImproperlyConfigured(f'Unrecognized currency type: {currency_type}')  # noqa: E501

        rounded_price = (total * chosen_currency_rate).quantize(rounding_base)
        final_price = to_wei(rounded_price, 'ether')

        return final_price

    def _update_session_payment_amount(self, request: HttpRequest, total):
        final_price = self._get_final_price(total, request.session['payment_ethereum_currency_type'])  # noqa: E501

        request.session['payment_ethereum_amount'] = final_price
        request.session['payment_ethereum_time'] = int(time.time())

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/pending.html')

        payment_is_valid = self._payment_is_valid_info(payment)
        ctx = {
            'payment_is_valid': payment_is_valid,
            'order': payment.order,
        }

        if not payment_is_valid:
            return template.render(ctx)

        wallet_address = WalletAddress.objects.get_for_order_payment(payment).hex_address
        currency_type = payment.info_data['currency_type']
        payment_amount = payment.info_data['amount']

        amount_in_ether_or_dai = from_wei(payment_amount, 'ether')

        if currency_type == 'ETH':
            erc_681_url = f'ethereum:{wallet_address}?value={payment_amount}'
            amount_manual = f'{amount_in_ether_or_dai} ETH'
            uniswap_url = f'https://v1.uniswap.exchange/send?exactField=output?exactAmount={amount_in_ether_or_dai}&inputCurrency=0x6b175474e89094c44da98b954eedeac495271d0f&outputCurrency=ETH&recipient={wallet_address}'  # noqa: E501
        elif currency_type == 'DAI':
            erc_681_url = f'ethereum:{DAI_MAINNET_ADDRESS}/transfer?address={wallet_address}&uint256={payment_amount}'  # noqa: E501
            amount_manual = f'{amount_in_ether_or_dai} DAI'
            uniswap_url = f'https://v1.uniswap.exchange/send?exactField=output?exactAmount={amount_in_ether_or_dai}&outputCurrency=0x6b175474e89094c44da98b954eedeac495271d0f&recipient={wallet_address}'  # noqa: E501

        else:
            raise ImproperlyConfigured(f'Unrecognized currency: {currency_type}')  # noqa: E501

        web3modal_url = f'https://checkout.web3modal.com/?currency={currency_type}&amount={amount_in_ether_or_dai}&to={wallet_address}'  # noqa: E501

        ctx.update({
            'erc_681_url': erc_681_url,
            'uniswap_url': uniswap_url,
            'web3modal_url': web3modal_url,
            'amount_manual': amount_manual,
            'wallet_address': wallet_address,
        })

        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/control.html')

        ctx = {
            'payment_info': payment.info_data,
        }

        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return False
