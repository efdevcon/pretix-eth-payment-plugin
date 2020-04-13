import logging

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope
from pretix.base.models.event import (
    Event,
)
from web3 import (
    Web3,
)
from web3.providers.auto import (
    load_provider_from_uri,
)

from pretix_eth.models import (
    WalletAddress,
)

logger = logging.getLogger(__name__)

SAI_ABI = [
    {'constant': True,
     'inputs': [{'name': '_owner', 'type': 'address'}],
     'name': 'balanceOf',
     'outputs': [{'name': 'balance', 'type': 'uint256'}],
     'type': 'function'},
]


class Command(BaseCommand):
    help = (
        'Verify pending orders from on-chain payments.  Performs a dry run '
        'by default.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '-s', '--slug',
            help='The slug of the event for which payments should be confirmed.',
        )
        parser.add_argument(
            '-n', '--no-dry-run',
            help='Modify database records to confirm payments.',
            action='store_true',
        )
        parser.add_argument(
            '-u', '--uri',
            help='A provider uri used to initialize web3.',
        )
        parser.add_argument(
            '-a', '--sai-address',
            help='The token address used to check for SAI payments.',
        )

    def handle(self, *args, **options):
        slug = options['slug']
        no_dry_run = options['no_dry_run']
        uri = options['uri']
        sai_address = options['sai_address']

        w3 = Web3(load_provider_from_uri(uri))
        sai_contract = w3.eth.contract(abi=SAI_ABI, address=sai_address)
        try:
            with scope(organizer=None):
                event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            raise ValueError(f'Event with slug "{slug}" not found')
        unconfirmed_addresses = WalletAddress.objects.all().for_event(event).unconfirmed_orders()

        for wallet_address in unconfirmed_addresses:
            hex_address = wallet_address.hex_address
            checksum_address = w3.toChecksumAddress(hex_address)

            order_payment = wallet_address.order_payment
            full_id = order_payment.full_id

            info = order_payment.info_data
            expected_currency_type = info['currency_type']
            expected_amount = info['amount']

            eth_amount = w3.eth.getBalance(checksum_address)
            sai_amount = sai_contract.functions.balanceOf(checksum_address).call()

            if eth_amount > 0 or sai_amount > 0:
                logger.info(f'Payments found for {full_id} at {checksum_address}:')

                if expected_currency_type == 'ETH':
                    if sai_amount > 0:
                        logger.warning(f'  * Found unexpected SAI payment of {sai_amount}')
                        logger.warning(f'  * Skipping')
                        continue
                    if eth_amount < expected_amount:
                        logger.warning(f'  * Expected payment of at least {expected_amount} {expected_currency_type}')  # noqa: E501
                        logger.warning(f'  * Given payment was only for {eth_amount}')
                        logger.warning(f'  * Skipping')
                        continue
                elif expected_currency_type == 'DAI':
                    if eth_amount > 0:
                        logger.warning(f'  * Found unexpected ETH payment of {eth_amount}')
                        logger.warning(f'  * Skipping')
                        continue
                    if sai_amount < expected_amount:
                        logger.warning(f'  * Expected payment of at least {expected_amount} {expected_currency_type}')  # noqa: E501
                        logger.warning(f'  * Given payment was only for {sai_amount}')
                        logger.warning(f'  * Skipping')
                        continue

                if no_dry_run:
                    logger.info(f'  * Confirming order payment {full_id}')
                    order_payment.confirm()
                else:
                    logger.info(f'  * DRY RUN: Would confirm order payment {full_id}')
            else:
                logger.info(f'No payments found for {full_id}')
