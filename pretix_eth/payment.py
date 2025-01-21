from decimal import Decimal
import logging
import time
import json
from collections import OrderedDict
import uuid
import requests

from django import forms
from django.urls import reverse
from django.http import HttpRequest
from django.template import RequestContext
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from pretix.base.models import OrderPayment, OrderRefund
from pretix.base.payment import BasePaymentProvider, PaymentProviderForm
from pretix.base.services.mail import mail_send

logger = logging.getLogger(__name__)

class DaimoPaymentForm(PaymentProviderForm):
    """Minimal payment form for Daimo Pay integration"""
    pass

class DaimoPay(BasePaymentProvider):
    identifier = "daimo_pay"
    verbose_name = _("Daimo Pay")
    public_name = _("Pay from any chain, any coin")
    # test_mode_message = "Paying in Test Mode"
    payment_form_class = DaimoPaymentForm

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
                    "DAIMO_PAY_WEBHOOK_SECRET",
                    forms.CharField(
                        label=_("Daimo Pay Webhook Secret"),
                        help_text=_("Secret token for verifying webhook requests"),
                    ),
                ),
                (
                    "DAIMO_PAY_RECIPIENT_ADDRESS", 
                    forms.CharField(
                        label=_("Recipient Address"),
                        help_text=_("Address to receive payments. Paid in DAI on Optimism"),
                    ),
                )
            ]
        )
        return form_fields

    # Validate config
    def is_allowed(self, request, **kwargs):
        api_key_configured = bool(
            self.settings.DAIMO_PAY_API_KEY is not None
            and len(self.settings.DAIMO_PAY_API_KEY) > 0
        )
        if not api_key_configured:
            logger.error("Daimo Pay API key not configured")

        webhook_secret_configured = bool(
            self.settings.DAIMO_PAY_WEBHOOK_SECRET is not None
            and len(self.settings.DAIMO_PAY_WEBHOOK_SECRET) > 0
        )
        if not webhook_secret_configured:
            logger.error("Daimo Pay webhook secret not configured")

        recipient_address_configured = bool(
            self.settings.DAIMO_PAY_RECIPIENT_ADDRESS is not None
            and len(self.settings.DAIMO_PAY_RECIPIENT_ADDRESS) > 0
        )
        if not recipient_address_configured:
            logger.error("Daimo Pay recipient address not configured")

        return all((
            api_key_configured,
            webhook_secret_configured,
            recipient_address_configured,
            super().is_allowed(request, **kwargs),
        ))

    # No need to collect payment information.
    def payment_form_render(self, request, total, order=None):
        self.settings.set('total', total)
        template = get_template('pretix_eth/checkout_payment_form.html')
        return template.render({})
    
    # We do not collect payment information. Instead, the user
    # pays via Daimo Pay directly on the "Review order" screen.
    def payment_is_valid_session(self, request):
        return True

    # Confirmation page: generate a Daimo Pay payment and let the user pay.
    def checkout_confirm_render(self, request):
        total = Decimal(self.settings.get('total'))
        payment_id = None
        print (f"checkout_confirm_render: creating Daimo Pay payment")  
        try:
            payment_id = self._create_daimo_pay_payment(total)
        except Exception as e:
            logger.error(f"Error in Daimo Pay API request: {str(e)}")
            raise e

        # TODO: this may not be the correct way to track Pretix session info.
        self.settings.set('payment_id', payment_id)

        template = get_template("pretix_eth/checkout_payment_confirm.html")
        return template.render({ "payment_id": payment_id })

    def _create_daimo_pay_payment(self, total: Decimal):
        # TODO: ideally set Idempotency-Key using the order code
        idempotency_key = str(uuid.uuid4())

        chain_op = 10
        token_op_dai = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"
        amount_dai = str(int(total * 1_000_000_000_000_000_000))

        request_data = {
            "intent": f"Purchase",
            "items": [],
            "recipient": {
                "address": self.settings.DAIMO_PAY_RECIPIENT_ADDRESS,
                "amount": amount_dai,
                "token": token_op_dai,
                "chain": chain_op,
            },
        }
        response = requests.post(
            "https://pay.daimo.com/api/generate",
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

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        # TODO: validate status + amount of payment ID for this order
        payment_id = self.settings.get('payment_id')
        print(f"execute_payment: {payment_id}")

        source_tx_hash, dest_tx_hash = self._get_daimo_pay_tx_hash(payment_id)
        print(f"execute_payment: {payment_id}: tx hashes {source_tx_hash} {dest_tx_hash}")
        if source_tx_hash != None:
            payment.confirm()
            payment.info_data = {
                "payment_id": payment_id,
                "source_tx_hash": source_tx_hash,
                "dest_tx_hash": dest_tx_hash,
                "amount": str(payment.amount),
                "time": int(time.time()),
            }
            payment.save(update_fields=["info"])
        else:
            payment.fail()
    
    def _get_daimo_pay_tx_hash(self, payment_id: str):
        response = requests.get(
            f"https://pay.daimo.com/api/payment/{payment_id}",
            headers={
                "Api-Key": self.settings.DAIMO_PAY_API_KEY,
            },
        )
        data = response.json()
        if response.status_code != 200:
            raise Exception(f"Daimo Pay API error: {response.text}")

        # TODO: clean up response typing
        print(repr(data))
        order = data['order']

        source_tx_hash = order.get('sourceInitiateTxHash')
        dest_tx_hash = order.get('destFastFinishTxHash')
        if dest_tx_hash is None:
            dest_tx_hash = order['destClaimTxHash']
        return source_tx_hash, dest_tx_hash

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/control.html")
        ctx = {
            "payment_info": payment.info_data,
        }
        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return True

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return True

    def execute_refund(self, refund: OrderRefund):
        # Send an email to the user, allowing them to claim the refund.
        email_addr = refund.order.email
        if email_addr is None:
            raise Exception("No email address found for refund order")
        
        # TODO: generate a refund secret
        # Save it to this order
        # Send an email with a link to a custom view
        # The view has a form to enter recipient address
        # Finally, user clicks refund, receives $x DAI back.
        # This atomically marks the refund as collected.
        
        print(f"PAY: sending refund email to {email_addr}")
        mail_send(
            to=[email_addr],
            subject="Refund claim instructions",
            body="Testing 123",
            html="Testing 1234",
            sender="support@daimo.com",
            order=refund.order,
        )
        
