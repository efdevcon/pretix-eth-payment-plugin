import logging
import json

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope

from pretix.base.models.event import (
    Event,
)

from pretix_eth.network.tokens import IToken, all_token_and_network_ids_to_tokens

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Verify pending orders from on-chain payments. Performs a dry run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-n",
            "--no-dry-run",
            help="Modify database records to confirm payments.",
            action="store_true",
        )

    def handle(self, *args, **options):
        no_dry_run = options["no_dry_run"]

        with scope(organizer=None):
            events = Event.objects.all()

        for event in events:
            self.confirm_payments_for_event(event, no_dry_run)

    def confirm_payments_for_event(self, event: Event, no_dry_run):
        logger.info(f"Event name - {event.name}")

        # todo pairing !!!!
        #unconfirmed_addresses = (
        #    WalletAddress.objects.all().for_event(event).unconfirmed_orders()
        #)

        # todo
        unconfirmed_addresses = []

        for wallet_address in unconfirmed_addresses:
            hex_address = wallet_address.hex_address

            order_payment = wallet_address.order_payment
            rpc_urls = json.loads(
                order_payment.payment_provider.settings.NETWORK_RPC_URL
            )
            full_id = order_payment.full_id

            info = order_payment.info_data
            token: IToken = all_token_and_network_ids_to_tokens[info["currency_type"]]
            expected_network_id = token.NETWORK_IDENTIFIER
            expected_network_rpc_url_key = f"{expected_network_id}_RPC_URL"
            network_rpc_url = None

            if expected_network_rpc_url_key in rpc_urls:
                network_rpc_url = rpc_urls[expected_network_rpc_url_key]
            else:
                logger.warning(
                    f"No RPC URL configured for {expected_network_id}. Skipping..."
                )
                continue

            expected_amount = info["amount"]

            # Get balance.
            balance = token.get_balance_of_address(hex_address, network_rpc_url)

            if balance > 0:
                logger.info(f"Payments found for {full_id} at {hex_address}:")
                if balance < expected_amount:
                    logger.warning(
                        f"  * Expected payment of at least {expected_amount} {token.TOKEN_SYMBOL}"
                    )
                    logger.warning(
                        f"  * Given payment was {balance} {token.TOKEN_SYMBOL}"
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
