import logging
import json

from django.core.management.base import (
    BaseCommand,
)
from django_scopes import scope

from web3 import Web3
from web3.providers.auto import load_provider_from_uri
from web3.exceptions import TransactionNotFound

from pretix.base.models import OrderPayment
from pretix.base.models.event import Event

from pretix_eth.network.tokens import IToken, all_token_and_network_ids_to_tokens, TOKEN_ABI

logger = logging.getLogger(__name__)


SAFETY_BLOCK_COUNT = 5


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
        log_verbosity = int(options.get('verbosity', 0))

        with scope(organizer=None):
            # todo change to events where pending payments are expected only?
            events = Event.objects.all()

        for event in events:
            self.confirm_payments_for_event(event, no_dry_run, log_verbosity)

    def confirm_payments_for_event(self, event: Event, no_dry_run, log_verbosity=0):
        logger.info(f"Event name - {event.name}")

        with scope(organizer=event.organizer):
            unconfirmed_order_payments = OrderPayment.objects.filter(
                order__event=event,
                state__in=(
                    OrderPayment.PAYMENT_STATE_CREATED,
                    OrderPayment.PAYMENT_STATE_PENDING,
                    OrderPayment.PAYMENT_STATE_CANCELED,
                )
            )
            if log_verbosity > 0:
                logger.info(f" * Found {unconfirmed_order_payments.count()} unconfirmed order payments")

        for order_payment in unconfirmed_order_payments:
            if log_verbosity > 0:
                logger.info(f" * trying to confirm payment: {order_payment} (has {order_payment.signed_messages.all().count()} signed messages)")
            # it is tempting to put .filter(invalid=False) here, but remember
            # there is still a chance that low-gas txs are mined later on.
            for signed_message in order_payment.signed_messages.all():
                rpc_urls = json.loads(
                    order_payment.payment_provider.settings.NETWORK_RPC_URL
                )
                full_id = order_payment.full_id

                info = order_payment.info_data
                token: IToken = all_token_and_network_ids_to_tokens[info["currency_type"]]
                expected_network_id = token.NETWORK_IDENTIFIER
                expected_network_rpc_url_key = f"{expected_network_id}_RPC_URL"

                if expected_network_rpc_url_key in rpc_urls:
                    network_rpc_url = rpc_urls[expected_network_rpc_url_key]
                else:
                    logger.warning(
                        f"No RPC URL configured for {expected_network_id}. Skipping..."
                    )
                    continue

                expected_amount = info["amount"]

                # Get balance
                w3 = Web3(load_provider_from_uri(network_rpc_url))
                if log_verbosity > 0:
                    logger.info(f"   * Looking for a receip for a transaction with hash={signed_message.transaction_hash}")
                try:
                    receipt = w3.eth.getTransactionReceipt(signed_message.transaction_hash)
                except TransactionNotFound:
                    if log_verbosity > 0:
                        logger.info(f"   * Transaction hash={signed_message.transaction_hash} not found, skipping.")
                    if signed_message.age > 30*60:
                        signed_message.invalidate()
                    continue

                if receipt.status == 0:
                    if log_verbosity > 0:
                        logger.info(f"   * Transaction hash={signed_message.transaction_hash} was has status=0, invalidating.")
                    signed_message.invalidate()
                    continue

                block_number = receipt.blockNumber

                if block_number is None or block_number + SAFETY_BLOCK_COUNT > w3.eth.get_block_number():
                    logger.warning(f"  * Transfer found in a block that is too young, waiting until at least {SAFETY_BLOCK_COUNT} more blocks are confirmed.")
                    continue

                if token.IS_NATIVE_ASSET:
                    # ETH
                    payment_amount = w3.eth.getTransaction(signed_message.transaction_hash).value
                else:
                    # DAI
                    contract = w3.eth.contract(address=token.ADDRESS, abi=TOKEN_ABI)
                    transaction_details = contract.events.Transfer().processReceipt(receipt)[0].args
                    payment_amount = transaction_details.value

                receipt_sender = getattr(receipt, 'from').lower()
                receipt_reciever = receipt.to.lower()
                correct_sender = receipt_sender == signed_message.sender_address.lower()
                correct_recipient = receipt_reciever == signed_message.recipient_address.lower()

                if not (correct_sender and correct_recipient):
                    logger.warning(
                        f"  * Transaction hash provided does not match correct sender and recipient"
                    )
                    if log_verbosity > 0:
                        logger.info(f"receipt sender={receipt_sender}, expected sender={signed_message.sender_address.lower()}")
                        logger.info(f"receipt recipient={receipt_reciever}, expected recipient={signed_message.recipient_address.lower()}")
                    continue

                if payment_amount > 0:
                    logger.info(f"Payments found for {full_id} at {signed_message.sender_address}:")
                    if payment_amount < expected_amount:
                        logger.warning(
                            f"  * Expected payment of at least {expected_amount} {token.TOKEN_SYMBOL}"
                        )
                        logger.warning(
                            f"  * Given payment was {payment_amount} {token.TOKEN_SYMBOL}"
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
