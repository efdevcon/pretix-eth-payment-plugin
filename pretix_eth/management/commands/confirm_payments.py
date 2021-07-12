import logging
import json

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope

from pretix.base.models.event import (
    Event,
)

from pretix_eth.models import (
    WalletAddress,
)
from pretix_eth.network.networks import all_network_ids_to_networks

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Verify pending orders from on-chain payments.  Performs a dry run "
        "by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-s",
            "--event-slug",
            help="The slug of the event for which payments should be confirmed.",
        )
        parser.add_argument(
            "-n",
            "--no-dry-run",
            help="Modify database records to confirm payments.",
            action="store_true",
        )

    def handle(self, *args, **options):
        slug = options["event_slug"]
        no_dry_run = options["no_dry_run"]

        try:
            with scope(organizer=None):
                event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            raise ValueError(f'Event with slug "{slug}" not found')
        unconfirmed_addresses = WalletAddress.objects.all().for_event(event).unconfirmed_orders()

        for wallet_address in unconfirmed_addresses:
            hex_address = wallet_address.hex_address

            order_payment = wallet_address.order_payment
            rpc_urls = json.loads(
                order_payment.payment_provider.settings.NETWORK_RPC_URL
            )
            full_id = order_payment.full_id

            info = order_payment.info_data
            currency_info = info["currency_type"].split("-")
            expected_currency_type = currency_info[0]
            expected_network_id = currency_info[1]
            expected_network_rpc_url_key = f"{expected_network_id}_RPC_URL"
            network_rpc_url = None

            if expected_network_rpc_url_key in rpc_urls:
                network_rpc_url = rpc_urls[expected_network_rpc_url_key]
            else:
                # TODO: Give an option for caller to add rpc url at run time.
                logger.error(f"RPC URL not configured for {expected_network_id}")
                continue

            expected_network = all_network_ids_to_networks[expected_network_id]
            expected_amount = info["amount"]

            # Get eth, token balance.
            eth_amount, token_amount = expected_network.get_currency_balance(
                hex_address, network_rpc_url
            )

            if eth_amount > 0 or token_amount > 0:
                logger.info(f"Payments found for {full_id} at {hex_address}:")

                if expected_currency_type == "ETH":
                    if token_amount > 0:
                        logger.warning(
                            f"  * Found unexpected payment of {token_amount} DAI"
                        )
                    if eth_amount < expected_amount:
                        logger.warning(
                            f"  * Expected payment of at least {expected_amount} ETH"
                        )
                        logger.warning(f"  * Given payment was {eth_amount} ETH")
                        logger.warning(f"  * Skipping")  # noqa: F541
                        continue
                elif expected_currency_type == "DAI":
                    if eth_amount > 0:
                        logger.warning(
                            f"  * Found unexpected payment of {eth_amount} ETH"
                        )
                    if token_amount < expected_amount:
                        logger.warning(
                            f"  * Expected payment of at least {expected_amount} DAI"
                        )  
                        logger.warning(
                            f"  * Given payment was {token_amount} DAI"
                        )  
                        logger.warning(f"  * Skipping")  # noqa: F541
                        continue

                if no_dry_run:
                    logger.info(f"  * Confirming order payment {full_id}")
                    with scope(organizer=None):
                        order_payment.confirm()
                else:
                    logger.info(f"  * DRY RUN: Would confirm order payment {full_id}")
            else:
                logger.info(f"No payments found for {full_id}")
