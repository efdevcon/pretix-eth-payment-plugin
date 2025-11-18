from decimal import Decimal
import logging
import time
from collections import OrderedDict
import uuid
import requests

from django import forms
from django.urls import reverse
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from pretix.base.models import OrderPayment, OrderRefund, Order
from pretix.base.payment import BasePaymentProvider, PaymentProviderForm, PaymentException
from pretix.base.services.mail import mail_send
from web3 import Web3

from pretix_eth.create_link import create_peanut_link

logger = logging.getLogger(__name__)

class DaimoPaymentForm(PaymentProviderForm):
    """Minimal payment form for Daimo Pay integration"""
    pass

class DaimoPay(BasePaymentProvider):
    identifier = "daimo_pay"
    verbose_name = _("Daimo Pay")
    public_name = _("Pay with crypto")
    # test_mode_message = "Paying in Test Mode"
    payment_form_class = DaimoPaymentForm

    # Admin settings for the plugin.
    @property
    def settings_form_fields(self):
        form_fields = OrderedDict(
            list(super().settings_form_fields.items())
            + [
                (
                    "DAIMO_PAY_API_KEY",
                    forms.CharField(
                        label=_("Daimo Pay API Key"),
                        help_text=_("API key for Daimo Pay integration"),
                    ),
                ),
                (
                    "DAIMO_PAY_RECIPIENT_ADDRESS",
                    forms.CharField(
                        label=_("Recipient Address"),
                        help_text=_("Address to receive payments. Paid in DAI on Optimism"),
                    ),
                ),
                (
                    "DAIMO_PAY_REFUND_EOA_PRIVATE_KEY",
                    forms.CharField(
                        label=_("Refund EOA Private Key"),
                        help_text=_("Private key for the EOA to send automated refunds. Must be funded with both ETH (for gas) and DAI (for refunds) on Optimism. If empty, automated refunds will not be available."),
                        required=False
                    ),
                )
            ]
        )
        return form_fields

    # Validate config
    def is_allowed(self, request, **kwargs):
        api_key_configured = bool(self.settings.DAIMO_PAY_API_KEY)
        if not api_key_configured:
            logger.error("Daimo Pay API key not configured")

        recipient_address_configured = bool(self.settings.DAIMO_PAY_RECIPIENT_ADDRESS)
        if not recipient_address_configured:
            logger.error("Daimo Pay recipient address not configured")
        elif not Web3.is_address(self.settings.DAIMO_PAY_RECIPIENT_ADDRESS):
            logger.error("Daimo Pay recipient address is invalid")
            recipient_address_configured = False

        return all((
            api_key_configured,
            recipient_address_configured,
            super().is_allowed(request, **kwargs),
        ))

    def _get_order_metadata(self, request) -> dict:
        """Get metadata for order including attendee email from cart or order"""
        attendee_email = None
        
        # Try to get from session cart
        print(f"session: {', '.join([f'{k}={repr(v)}' for k, v in request.session.items()])}")
        event_id = self.event.id
        cart_id = request.session.get(f'current_cart_event_{event_id}')
        if cart_id and 'carts' in request.session and cart_id in request.session['carts']:
            cart = request.session['carts'][cart_id]
            if 'email' in cart:
                attendee_email = cart['email']
        
        # If not found, try to get from order
        if not attendee_email:
            try:
                # Extract order_id from URL path
                path = request.path
                if '/order/' in path:
                    order_id = path.split('/order/')[1].split('/')[0]
                    order = Order.objects.get(code=order_id, event=self.event)
                    attendee_email = order.email
            except Exception as e:
                logger.error(f"error fetching order email: {e}")

        return {
            "event_id": str(self.event.id),
            "event_slug": str(self.event.slug),
            "attendee_email": attendee_email or "",
        }

    # Payment screen: just a message saying continue to payment.
    # No need to collect payment information.
    def payment_form_render(self, request, total):
        request.session['total_usd'] = str(total)

        metadata = self._get_order_metadata(request)
        payment_id = self._create_daimo_pay_payment(total, metadata)

        print(f"payment_form_render: total {total}, new payment_id {payment_id}, metadata ${repr(metadata)}")
        request.session['payment_id'] = payment_id

        template = get_template('pretix_eth/checkout_payment_form.html')
        return template.render({})
    
    # We do not collect payment information. Instead, the user
    # pays via Daimo Pay directly on the "Review order" screen.
    def payment_is_valid_session(self, request):
        return True

    # Confirmation page: generate a Daimo Pay payment and let the user pay.
    def checkout_confirm_render(self, request):
        print (f"checkout_confirm_render: creating Daimo Pay payment")  
        total = Decimal(request.session['total_usd'])
        payment_id = request.session['payment_id']
        print (f"checkout_confirm_render: total {total}, payment id {payment_id}")
        template = get_template("pretix_eth/checkout_payment_confirm.html")
        return template.render({ "payment_id": payment_id })

    def _create_daimo_pay_payment(self, total: Decimal, metadata: dict) -> str:
        idempotency_key = str(uuid.uuid4())
        chain_op = 10
        token_op_dai = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"
        request_data = {
            "display": {
                "intent": f"Purchase",
                "paymentOptions": ["AllWallets", "AllAddresses"],
            },
            "destination": {
                "destinationAddress": self.settings.DAIMO_PAY_RECIPIENT_ADDRESS,
                "chainId": chain_op,
                "tokenAddress": token_op_dai,
                "amountUnits": str(total),
            },
            "metadata": metadata,
        }
        response = requests.post(
            "https://pay.daimo.com/api/payment",
            headers={
                "Api-Key": self.settings.DAIMO_PAY_API_KEY,
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key
            },
            json=request_data,
        )

        data = response.json()
        if response.status_code != 200 or not data.get("id") or not data.get("url"):
            raise Exception(f"Daimo Pay API error: {response.text}")

        return data["id"]

    # Called *after* the user clicks Place Order on the Confirm screen.
    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment_id = request.session['payment_id']
        print(f"execute_payment: {payment_id}")
        request.session['payment_id'] = ''
        self.confirm_payment_by_id(payment_id, payment)

    def confirm_payment_by_id(self, payment_id: str, payment: OrderPayment) -> None:
        # Ensure that it's paid
        n_tries = 5
        for i in range(n_tries):
            source_chain_id, source_tx_hash, dest_chain_id, dest_tx_hash = self._fetch_payment_by_id(payment_id)

            # If the payment is not yet paid, sleep and retry with exponential backoff
            if source_tx_hash == None and dest_tx_hash == None:
                if i == n_tries - 1:
                    break
                sleep_time = 2**i
                print(f"confirm_payment_by_id: {payment_id}: not yet paid, sleeping {sleep_time} seconds")
                time.sleep(sleep_time)
                continue

            # Finished, confirm the payment and exit
            print(f"confirm_payment_by_id: {payment_id}: source {source_chain_id}-{source_tx_hash}, dest {dest_chain_id}-{dest_tx_hash}")
            payment.confirm()
            payment.info_data = {
                "payment_id": payment_id,
                "source_tx_hash": source_tx_hash,
                "dest_tx_hash": dest_tx_hash,
                "source_chain_id": source_chain_id,
                "dest_chain_id": dest_chain_id,
                "amount": str(payment.amount),
                "time": int(time.time()),
            }
            payment.save(update_fields=["info"])
            return

        print(f"execute_payment: {payment_id}: FAIL, not finished according to Daimo Pay API")
        payment.fail()


    def _fetch_payment_by_id(self, payment_id: str):
        response = requests.get(
            f"https://pay.daimo.com/api/payment/{payment_id}",
            headers={
                "Api-Key": self.settings.DAIMO_PAY_API_KEY,
            },
        )
        data = response.json()
        if response.status_code != 200:
            raise Exception(f"Daimo Pay API error: {response.text}")

        # See https://paydocs.daimo.com/payments-api#retrieve-a-payment-by-id
        print(repr(data))
        source = data['source']
        dest = data['destination']
        source_chain_id = source and source['chainId']
        source_tx_hash = source and source['txHash']
        dest_chain_id = dest['chainId']
        dest_tx_hash = dest['txHash']
        return source_chain_id, source_tx_hash, dest_chain_id, dest_tx_hash

    # Admin display: show order payment details
    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/control.html")
        ctx = {
            "payment_info": payment.info_data,
        }
        return template.render(ctx)

    abort_pending_allowed = True

    # Admin: allow automated refunds
    def payment_refund_supported(self, payment: OrderPayment):
        return bool(self.settings.DAIMO_PAY_REFUND_EOA_PRIVATE_KEY)

    # Admin: allow partial refunds
    def payment_partial_refund_supported(self, payment: OrderPayment):
        return self.payment_refund_supported(payment)

    # Admin: execute a refund
    def execute_refund(self, refund: OrderRefund):
        # Send an email to the user, allowing them to claim the refund.
        email_addr = refund.order.email
        if email_addr is None:
            raise Exception("No email address found for refund order")
        
        try:
            print(f"PAY: creating refund link for {refund.order.code}: ${refund.amount}")
            link = create_peanut_link(refund.amount, self.settings.DAIMO_PAY_REFUND_EOA_PRIVATE_KEY)
            print(f"PAY: refunding {refund.order.code} to {email_addr}: {link}")

            amount_str = f"{refund.amount:.2f}"
            body_text = f"Hi there,\n\nYour order to the Devconnect ARG Ethereum World's Fair has been refunded.\n\nClaim your refund of ${amount_str} here: {link}\n\nThanks,\nDevconnect Team"
            body_html = f"Hi there,<br><br>Your order to the Devconnect ARG Ethereum World's Fair has been refunded.<br><br>Claim your refund of ${amount_str} here: <a href='{link}'>{link}</a><br><br>Thanks,<br>Devconnect Team"

            mail_send(
                to=[email_addr],
                subject=f"Refund for Order #{refund.order.code}",
                body=body_text,
                html=body_html,
                sender="support@devconnect.org",
                event=refund.order.event_id,
                order=refund.order.id
            )
            print(f"PAY: sent email to {email_addr}: {body_text}")

            refund.done()
            print(f"PAY: refund {refund.order.code} complete")
        except Exception as e:
            raise PaymentException(f"error creating & sending refund link: {str(e)}")