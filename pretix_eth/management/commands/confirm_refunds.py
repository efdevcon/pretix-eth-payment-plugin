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

from pretix.base.models import (
    OrderRefund,
)

logger = logging.getLogger(__name__)

TOKEN_ABI = [
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
            '-s', '--event-slug',
            help='The slug of the event for which payments should be confirmed.',
        )
        parser.add_argument(
            '-n', '--no-dry-run',
            help='Modify database records to confirm payments.',
            action='store_true',
        )
        parser.add_argument(
            '-u', '--web3-provider-uri',
            help='A provider uri used to initialize web3.',
        )
        parser.add_argument(
            '-a', '--token-address',
            help='The token address used to check for token payments.',
        )

    def handle(self, *args, **options):
        slug = options['event_slug']
        no_dry_run = options['no_dry_run']
        uri = options['web3_provider_uri']
        token_address = options['token_address']

        w3 = Web3(load_provider_from_uri(uri))
        token_contract = w3.eth.contract(abi=TOKEN_ABI, address=token_address)

        try:
            with scope(organizer=None):
                event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            raise ValueError(f'Event with slug "{slug}" not found')

        unconfirmed_addresses = WalletAddress.objects.all().for_event(event).unconfirmed_refunds()

        for wallet_address in unconfirmed_addresses:
            hex_address = wallet_address.hex_address
            checksum_address = w3.toChecksumAddress(hex_address)

            order_refund = OrderRefund.objects.get(payment=wallet_address.order_payment)
            full_id = order_refund.full_id

            info = order_refund.info_data
            expected_currency_type = info['currency_type']

            eth_amount = w3.eth.getBalance(checksum_address)
            token_amount = token_contract.functions.balanceOf(checksum_address).call()

            if (eth_amount == 0 and expected_currency_type == 'ETH') or (
                    token_amount == 0 and expected_currency_type == 'DAI'):
                logger.info(f'Refund found for {full_id} at {checksum_address}:')

                if no_dry_run:
                    logger.info(f'  * Confirming refund payment {full_id}')
                    with scope(organizer=None):
                        order_refund.done()
                else:
                    logger.info(f'  * DRY RUN: Would confirm order payment {full_id}')
            else:
                logger.info(f'No refund process started for {full_id}')
