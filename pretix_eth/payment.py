import decimal
import logging
import time
from collections import OrderedDict

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from eth_utils import (
    import_string,
)
from requests.exceptions import ConnectionError

from pretix.base.models import OrderPayment
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

RESERVED_ORDER_DIGITS = 5

DAI_MAINNET_ADDRESS = '0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'


def truncate_wei_value(value: int, digits: int) -> int:
    multiplier = 10 ** digits
    return int(round(value / multiplier) * multiplier)


class Ethereum(BasePaymentProvider):
    identifier = 'ethereum'
    verbose_name = _('Ethereum')
    public_name = _('Ethereum')

    @cached_property
    def transaction_provider(self) -> TransactionProviderAPI:
        transaction_provider_path = self.settings.get('TRANSACTION_PROVIDER')

        try:
            transaction_provider_class = import_string(transaction_provider_path)
        except ImportError:
            transaction_provider_class = import_string(DEFAULT_TRANSACTION_PROVIDER)

        return transaction_provider_class()

    @cached_property
    def token_provider(self) -> TokenProviderAPI:
        token_provider_path = self.settings.get('TOKEN_PROVIDER')

        try:
            token_provider_class = import_string(token_provider_path)
        except ImportError:
            token_provider_class = import_string(DEFAULT_TOKEN_PROVIDER)

        return token_provider_class()

    @property
    def settings_form_fields(self):
        form_fields = OrderedDict(
            list(super().settings_form_fields.items())
            + [
                ('WALLET_ADDRESS', forms.CharField(
                    label=_('Wallet address'),
                    required=True
                )),
                ('ETH_RATE', forms.DecimalField(
                    label=_('Ethereum rate'),
                    help_text=_('Specify the exchange rate between Ethereum and your base currency. Leave out if you do not want to accept ETH'),  # noqa: E501
                    required=False
                )),
                ('xDAI_RATE', forms.DecimalField(
                    label=_('xDAI rate'),
                    help_text=_('Specify the exchange rate between xDAI and your base currency. Leave out if you do not want to accept DAI'),  # noqa: E501
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

        form_fields.move_to_end('WALLET_ADDRESS', last=True)
        form_fields.move_to_end('ETH_RATE', last=True)
        form_fields.move_to_end('xDAI_RATE', last=True)
        form_fields.move_to_end('TRANSACTION_PROVIDER', last=True)
        form_fields.move_to_end('TOKEN_PROVIDER', last=True)

        return form_fields

    def is_allowed(self, request, **kwargs):
        settings_configured = all((
            self.settings.WALLET_ADDRESS,
            self.settings.ETH_RATE,
            self.settings.xDAI_RATE,
        ))

        return settings_configured and super().is_allowed(request)

    @property
    def payment_form_fields(self):
        currency_type_choices = (
            ('DAI', _('DAI')),
            ('ETH', _('ETH')),
        )

        form_fields = OrderedDict(
            list(super().payment_form_fields.items())
            + [
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
            self._get_rates_checkout(request, cart['total'])
            return True

        return False

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        form = self.payment_form(request)

        if form.is_valid():
            request.session['payment_ethereum_currency_type'] = form.cleaned_data['currency_type']  # noqa: E501
            return True

        return False

    def payment_is_valid_session(self, request):
        return all((
            'payment_ethereum_currency_type' in request.session,
            'payment_ethereum_time' in request.session,
            'payment_ethereum_amount' in request.session,
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

    def _get_rates_from_api(self, total, currency):
        try:
            if currency == 'ETH':
                final_price = to_wei((
                    total * decimal.Decimal(self.settings.ETH_RATE)
                ).quantize(decimal.Decimal('1.00000')), 'ether')
            elif currency == 'DAI':
                final_price = to_wei((
                    total * decimal.Decimal(self.settings.xDAI_RATE)
                ).quantize(decimal.Decimal('1.00000')), 'ether')
            else:
                raise ImproperlyConfigured("Unrecognized currency: {0}".format(self.event.currency))

            return final_price
        except ConnectionError:
            logger.exception('Internal eror occured.')
            raise PaymentException(
                _('Please try again and get in touch with us if this problem persists.')
            )

    def _get_rates_checkout(self, request: HttpRequest, total):
        final_price = self._get_rates_from_api(total, request.session['payment_ethereum_currency_type'])  # noqa: E501

        request.session['payment_ethereum_amount'] = truncate_wei_value(final_price, RESERVED_ORDER_DIGITS)
        request.session['payment_ethereum_time'] = int(time.time())

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template('pretix_eth/pending.html')

        wallet_address = self.settings.WALLET_ADDRESS
        currency_type = payment.info_data['currency_type']

        truncated_amount_in_wei = payment.info_data['amount']
        amount_plus_payment_id = truncated_amount_in_wei + payment.id
        amount_in_ether = from_wei(amount_plus_payment_id, 'ether')

        if currency_type == 'ETH':
            erc_681_url = f'ethereum:{wallet_address}?value={amount_plus_payment_id}'
        elif currency_type == 'DAI':
            erc_681_url = f'ethereum:{DAI_MAINNET_ADDRESS}/transfer?address={wallet_address}&uint256={amount_plus_payment_id}'  # noqa: E501
        else:
            raise ImproperlyConfigured(f'Unrecognized currency: {currency_type}')  # noqa: E501

        web3connect_url = f'https://checkout.web3connect.com/?currency={currency_type}&amount={amount_in_ether}&to={wallet_address}'  # noqa: E501

        ctx = {
            'erc_681_url': erc_681_url,
            'web3connect_url': web3connect_url
        }

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
