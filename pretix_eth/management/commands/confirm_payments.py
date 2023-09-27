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
import requests

from pretix_eth.network.tokens import (
    IToken,
    all_token_and_network_ids_to_tokens,
    TOKEN_ABI,
)

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
        log_verbosity = int(options.get("verbosity", 0))

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
                ),
            )
            if log_verbosity > 0:
                logger.info(
                    f" * Found {unconfirmed_order_payments.count()} "
                    f"unconfirmed order payments"
                )

        for order_payment in unconfirmed_order_payments:
            try:
                if log_verbosity > 0:
                    logger.info(
                        f" * trying to confirm payment: {order_payment} "
                        f"(has {order_payment.signed_messages.all().count()} signed messages)"
                    )
                # it is tempting to put .filter(invalid=False) here, but remember
                # there is still a chance that low-gas txs are mined later on.
                for signed_message in order_payment.signed_messages.all():
                    rpc_urls = json.loads(
                        order_payment.payment_provider.settings.NETWORK_RPC_URL
                    )
                    full_id = order_payment.full_id

                    info = order_payment.info_data
                    try:
                        token: IToken = all_token_and_network_ids_to_tokens[
                            info["currency_type"]
                        ]
                    except KeyError:
                        logger.info(f"info['currency_type'] = {info['currency_type']}")
                        logger.warning("Invalid network, invalidating signed message and skipping.")
                        signed_message.invalidate()
                        continue

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
                    transaction_hash = signed_message.transaction_hash
                    is_safe_app_tx = signed_message.safe_app_transaction_url

                    if log_verbosity > 0:
                        if is_safe_app_tx:
                            logger.info(
                                f"   * Processing safe app transaction with "
                                f"safe_internal_tx_url={signed_message.safe_app_transaction_url}"
                            )
                        else:
                            logger.info(
                                f"   * Looking for a receipt for a transaction with "
                                f"hash={transaction_hash}"
                            )

                    try:
                        # Custom safe transaction handling - can be removed once we create a smart contract for payment handling # noqa: E501
                        if signed_message.safe_app_transaction_url:
                            try:
                                resp = requests.get(signed_message.safe_app_transaction_url)

                                jsonResp = resp.json()

                                if jsonResp.get('isExecuted') and jsonResp.get('isSuccessful'):
                                    safe_tx_sender = jsonResp.get('safe').lower()
                                    safe_tx_receiver = jsonResp.get('to')
                                    payment_amount = int(jsonResp.get('value'))
                                    transaction_hash = jsonResp.get('transactionHash')
                                else:
                                    if log_verbosity > 0:
                                        logger.info(
                                            f"   * Safe App Transaction"
                                            f" safe_tx={signed_message.safe_app_transaction_url} did not execute/is not succesful,"  # noqa: E501
                                            f" skipping."
                                        )

                                    if signed_message.age > order_payment.payment_provider.settings.get('PAYMENT_NOT_RECIEVED_RETRY_TIMEOUT', as_type=float):  # noqa: E501
                                        signed_message.invalidate()
                                    continue
                            except Exception:
                                if log_verbosity > 0:
                                    logger.info(
                                        f"   * Safe App Transaction"
                                        f" safe_tx={signed_message.safe_app_transaction_url} could not be processed,"  # noqa: E501
                                        f" skipping."
                                    )

                                if signed_message.age > order_payment.payment_provider.settings.get('PAYMENT_NOT_RECIEVED_RETRY_TIMEOUT', as_type=float):  # noqa: E501
                                    signed_message.invalidate()
                                continue

                        receipt = w3.eth.get_transaction_receipt(
                            transaction_hash
                        )
                    except TransactionNotFound:
                        if log_verbosity > 0:
                            logger.info(
                                f"   * Transaction"
                                f" hash={transaction_hash} not found,"
                                f" skipping."
                            )

                        if signed_message.age > order_payment.payment_provider.settings.get('PAYMENT_NOT_RECIEVED_RETRY_TIMEOUT', as_type=float):  # noqa: E501
                            signed_message.invalidate()
                        continue

                    if receipt.status == 0:
                        if log_verbosity > 0:
                            logger.info(
                                f"   * Transaction hash={transaction_hash}"
                                f" was has status=0, invalidating."
                            )
                        signed_message.invalidate()
                        continue

                    block_number = receipt.blockNumber

                    safety_block_count = order_payment.payment_provider.settings.get(
                        'SAFETY_BLOCK_COUNT',
                        as_type=int,
                        default=10,
                    )

                    if (
                            block_number is None
                            or block_number + safety_block_count > w3.eth.get_block_number()
                    ):
                        logger.warning(
                            f"  * Transfer found in a block that is too young, "
                            f"waiting until at least {safety_block_count} more blocks are confirmed."
                        )
                        continue

                    if token.IS_NATIVE_ASSET:
                        # ETH
                        if is_safe_app_tx:
                            receipt_receiver = safe_tx_receiver
                        else:
                            receipt_receiver = receipt.to.lower()

                            payment_amount = w3.eth.get_transaction(
                                transaction_hash
                            ).value

                        correct_recipient = (
                            receipt_receiver == signed_message.recipient_address.lower()
                        )

                    else:
                        # DAI
                        contract = w3.eth.contract(address=token.ADDRESS,
                                                   abi=TOKEN_ABI)

                        # This may warn about mismatched ABI if its a smart contract wallet tx because of intermediary function calls - but it'll still process the Transfer event correctly # noqa: E501
                        transaction_details = (
                            contract.events.Transfer().processReceipt(receipt)[0].args
                        )

                        payment_amount = transaction_details.value
                        receipt_receiver = transaction_details.to.lower()

                        # Safe has intermediary function calls (which is not the token address), so we'll need to pull the receiver address from the internal safe transaction rather than the tx receipt # noqa: E501
                        if is_safe_app_tx:
                            correct_contract = token.ADDRESS.lower() == safe_tx_receiver.lower()
                        else:
                            correct_contract = token.ADDRESS.lower() == receipt.to.lower()

                        correct_recipient = correct_contract and (
                            receipt_receiver == signed_message.recipient_address.lower())

                    if is_safe_app_tx:
                        receipt_sender = safe_tx_sender
                    else:
                        receipt_sender = getattr(receipt, "from").lower()

                    correct_sender = receipt_sender == signed_message.sender_address.lower()

                    if not (correct_sender and correct_recipient):
                        logger.warning(
                            "  * Transaction hash provided does not match "
                            "correct sender and recipient"
                        )
                        if log_verbosity > 0:
                            logger.info(
                                f"receipt sender={receipt_sender}, "
                                f"expected sender={signed_message.sender_address.lower()}"
                            )
                            logger.info(
                                f"receipt recipient={receipt_receiver}, "
                                f"expected recipient={signed_message.recipient_address.lower()}"
                            )
                        continue

                    if payment_amount > 0:
                        logger.info(
                            f"Payments found for {full_id} at {signed_message.sender_address}:"
                        )
                        if payment_amount < expected_amount:
                            logger.warning(
                                f"  * Expected payment of at least"
                                f" {expected_amount} {token.TOKEN_SYMBOL}"
                            )
                            logger.warning(
                                f"  * Given payment was"
                                f" {payment_amount} {token.TOKEN_SYMBOL}"
                            )
                            logger.warning(f"  * Skipping")  # noqa: F541
                            continue
                        if no_dry_run:
                            logger.info(f"  * Confirming order payment {full_id}")
                            with scope(organizer=None):
                                order_payment.confirm()
                            signed_message.is_confirmed = True
                            signed_message.save()
                        else:
                            logger.info(
                                f"  * DRY RUN: Would confirm order payment {full_id}"
                            )
                    else:
                        logger.info(f"No payments found for {full_id}")
            except Exception as e:
                logger.warning(f"An unhandled error occurred for order: {order_payment}")
                logger.warning(e)
