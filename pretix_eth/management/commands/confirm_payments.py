import logging
import os
from typing import (
    Tuple,
    Union,
)

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope
from eth_utils import (
    to_hex,
    to_normalized_address,
)
from pretix.base.models.event import (
    Event,
)
from pretix.base.models.orders import (
    OrderPayment,
)

from pretix_eth.exceptions import (
    TransactionProviderError,
)
from pretix_eth.payment import (
    Ethereum,
    DAI_MAINNET_ADDRESS,
    RESERVED_ORDER_DIGITS,
)
from pretix_eth.providers import (
    BlockscoutMainnetProvider,
    EtherscanGoerliProvider,
    EtherscanMainnetProvider,
    EtherscanRopstenProvider,
    Transaction,
    Transfer,
)

logger = logging.getLogger(__name__)

TXN_PROVIDERS = {
    'etherscan-mainnet': EtherscanMainnetProvider,
    'etherscan-ropsten': EtherscanRopstenProvider,
    'etherscan-goerli': EtherscanGoerliProvider,
    'blockscout-mainnet': BlockscoutMainnetProvider,
}

PAYMENT_ID_WEI = 10 ** (18 - RESERVED_ORDER_DIGITS)


def payment_id_from_wei(value: int) -> int:
    value_minus_id = (value // PAYMENT_ID_WEI) * PAYMENT_ID_WEI
    payment_id = value - value_minus_id

    if payment_id <= 0:
        raise ValueError(f'Invalid payment id {payment_id}')
    else:
        return payment_id


class Command(BaseCommand):
    help = (
        'Verify pending orders from on-chain payments.  Performs a dry run '
        'by default.'
    )

    def add_arguments(self, parser):
        wallet_group = parser.add_mutually_exclusive_group(required=True)
        wallet_group.add_argument(
            '--event-slug',
            help=(
                'The slug of the event for which payments should be confirmed.  '
                'This is used to determine the wallet address to check for '
                'payments.'
            ),
        )
        wallet_group.add_argument(
            '--wallet-address',
            help='An explicit wallet address to inspect for payment transactions.',
        )
        parser.add_argument(
            '--token-address',
            help=(
                'An ERC20 token address to inspect for token transfers.  '
                'Default is the DAI mainnet address.'
            ),
            default=DAI_MAINNET_ADDRESS,
        )
        parser.add_argument(
            '--api',
            help='The api to use for transaction fetching.',
            default='blockscout-mainnet',
            choices=TXN_PROVIDERS.keys(),
        )
        parser.add_argument(
            '--no-dry-run',
            help='Modify database records to confirm payments.',
            action='store_true',
        )
        parser.add_argument(
            '--start-block',
            help='The start block of the range of transactions to inspect for payments.',
            type=int,
        )
        parser.add_argument(
            '--end-block',
            help='The end block of the range of transactions to inspect for payments.',
            type=int,
        )

    @classmethod
    def confirm_from_results(cls,
                             results: Union[Tuple[Transaction, ...], Tuple[Transfer, ...]],
                             expected_currency_type: str,
                             no_dry_run: bool = True) -> None:
        """
        Takes a sequence of transactions or token transfers and confirms
        payments that match the payment id found in their wei values.
        """
        with scope(organizer=None):
            for res in results:
                typ_repr = type(res).__name__
                hsh_repr = to_hex(res.hash)
                val_repr = str(res.value)
                result_repr = f'{typ_repr}(hash={hsh_repr}, value={val_repr})'

                logger.info(f'Attempting to confirm payment from {result_repr}:')

                try:
                    payment_id = payment_id_from_wei(res.value)
                except ValueError as e:
                    logger.warning(f'  * {e.args[0]}')
                    logger.warning(f'  * Skipping')
                    continue

                logger.info(f'  * Payment id is {payment_id}')

                try:
                    order_payment = OrderPayment.objects.get(id=payment_id)
                except OrderPayment.DoesNotExist:
                    logger.warning(f"  * Couldn't find order payment with id {payment_id}")
                    logger.warning(f'  * Skipping')
                    continue

                info = order_payment.info_data
                currency_type = info['currency_type']
                amount = info['amount']

                if currency_type != expected_currency_type:
                    logger.warning(f'  * Order payment {order_payment.id} was expecting payment in {currency_type}!!!')  # noqa: E501
                    logger.warning(f'  * Given payment was in {expected_currency_type}')
                    logger.warning(f'  * Skipping')
                    continue

                if res.value < amount:
                    logger.warning(f'  * Order payment {order_payment.id} was expecting payment of at least {amount}!!!')  # noqa: E501
                    logger.warning(f'  * Given payment was only for {res.value}')
                    logger.warning(f'  * Skipping')
                    continue

                if no_dry_run:
                    logger.info(f'  * Confirming order payment {order_payment.id}')
                    order_payment.confirm()
                else:
                    logger.info(f'  * DRY RUN: Would confirm order payment {order_payment.id}')

    def handle(self, *args, **options):
        no_dry_run = options['no_dry_run']
        start_block = options['start_block']
        end_block = options['start_block']
        token_address = options['token_address']

        # Instantiate transaction provider based on chosen API
        api = options['api']
        txn_provider_class = TXN_PROVIDERS[api]
        if api.startswith('etherscan-'):
            try:
                api_key = os.environ['ETHERSCAN_API_KEY']
            except KeyError:
                raise ValueError('Etherscan api key not found in "ETHERSCAN_API_KEY" env var')
            txn_provider = txn_provider_class(api_key=api_key)
        else:
            txn_provider = txn_provider_class()

        # Determine wallet address
        event_slug = options['event_slug']
        if event_slug is not None:
            try:
                event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist:
                raise ValueError(f'Event with slug "{event_slug}" not found')
            payment_provider = Ethereum(event)
            raw_wallet_address = payment_provider.settings.WALLET_ADDRESS
        else:
            raw_wallet_address = options['wallet_address']
        wallet_address = to_normalized_address(raw_wallet_address)

        # Get external transactions for wallet address
        logger.info(f'Fetching external ether transactions for {wallet_address}...')
        try:
            external_txns = txn_provider.get_transaction_list(
                wallet_address,
                start_block=start_block,
                end_block=end_block,
            )
        except TransactionProviderError as e:
            logger.error(f'...error: {e.args[0]}')
        else:
            logger.info(f'...found {len(external_txns)} transactions.')
            self.confirm_from_results(external_txns, 'ETH', no_dry_run=no_dry_run)

        # Get internal transactions for wallet address
        logger.info(f'Fetching internal ether transactions for {wallet_address}...')
        try:
            internal_txns = txn_provider.get_internal_transaction_list(
                wallet_address,
                start_block=start_block,
                end_block=end_block,
            )
        except TransactionProviderError as e:
            logger.error(f'...error: {e.args[0]}')
        else:
            logger.info(f'...found {len(internal_txns)} transactions.')
            self.confirm_from_results(internal_txns, 'ETH', no_dry_run=no_dry_run)

        # Get token transfers for wallet address
        logger.info(
            f'Fetching token transfers (for token contract at {token_address}) '
            f'for {wallet_address}...'
        )
        try:
            transfers = txn_provider.get_transfer_list(
                wallet_address,
                token_address,
                start_block=start_block,
                end_block=end_block,
            )
        except TransactionProviderError as e:
            logger.error(f'...error: {e.args[0]}')
        else:
            logger.info(f'...found {len(transfers)} transfers.')
            self.confirm_from_results(transfers, 'DAI', no_dry_run=no_dry_run)
