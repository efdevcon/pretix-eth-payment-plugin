import logging
import json

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope

from pretix.base.models.event import (
    Event,
)
from pretix.base.models import (
    OrderRefund,
)

from pretix_eth.models import (
    WalletAddress,
)
from pretix_eth.network.tokens import IToken, all_token_and_network_ids_to_tokens

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Verify pending refunds from on-chain payments.  Performs a dry run "
        "by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-s",
            "--event-slug",
            help="The slug of the event for which refunds should be confirmed.",
        )
        parser.add_argument(
            "-n",
            "--no-dry-run",
            help="Modify database records to confirm refunds.",
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

        unconfirmed_addresses = WalletAddress.objects.all().for_event(event).unconfirmed_refunds()

        for wallet_address in unconfirmed_addresses:
            hex_address = wallet_address.hex_address

            order_refund = OrderRefund.objects.get(payment=wallet_address.order_payment)
            rpc_urls = json.loads(
                order_refund.payment_provider.settings.NETWORK_RPC_URL
            )
            full_id = order_refund.full_id

            info = order_refund.info_data
            token: IToken = all_token_and_network_ids_to_tokens[info["currency_type"]]
            expected_network_id = token.NETWORK_IDENTIFIER
            expected_network_rpc_url_key = f"{expected_network_id}_RPC_URL"
            network_rpc_url = None

            if expected_network_rpc_url_key in rpc_urls:
                network_rpc_url = rpc_urls[expected_network_rpc_url_key]
            else:
                # TODO: Give an option for caller to add rpc url at run time.
                logger.error(f"RPC URL not configured for {expected_network_id}. Skipping...")
                continue

            # Get balance.
            balance = token.get_balance_of_address(hex_address, network_rpc_url)

            if (balance == 0):
                logger.info(f"Refund found for {full_id} at {hex_address}:")
                if no_dry_run:
                    logger.info(f"  * Confirming refund payment {full_id}")
                    with scope(organizer=None):
                        order_refund.done()
                else:
                    logger.info(f"  * DRY RUN: Would confirm order payment {full_id}")
            else:
                logger.info(f"No refund process started for {full_id}")
