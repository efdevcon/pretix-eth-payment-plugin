import logging
import time
import json
from collections import OrderedDict
import requests

from django import forms
from django.urls import reverse
from django.http import HttpRequest
from django.template import RequestContext
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from pretix.base.models import OrderPayment, OrderRefund
from pretix.base.payment import BasePaymentProvider, PaymentProviderForm

logger = logging.getLogger(__name__)

class DaimoPaymentForm(PaymentProviderForm):
    """Minimal payment form for Daimo Pay integration"""
    pass

class DaimoPay(BasePaymentProvider):
    identifier = "daimo_pay"
    verbose_name = _("Daimo Pay")
    public_name = _("Daimo Pay")
    test_mode_message = "Paying in Test Mode"
    payment_form_class = DaimoPaymentForm

    @property
    def settings_form_fields(self):
        form_fields = OrderedDict(
            list(super().settings_form_fields.items())
            + [
                (
                    "DAIMO_API_KEY",
                    forms.CharField(
                        label=_("Daimo Pay API Key"),
                        help_text=_("API key for Daimo Pay integration"),
                    ),
                ),
                (
                    "DAIMO_WEBHOOK_SECRET",
                    forms.CharField(
                        label=_("Daimo Pay Webhook Secret"),
                        help_text=_("Secret token for verifying webhook requests"),
                    ),
                ),
            ]
        )
        return form_fields

    def is_allowed(self, request, **kwargs):
        api_key_configured = bool(
            self.settings.DAIMO_API_KEY is not None
            and len(self.settings.DAIMO_API_KEY) > 0
        )
        if not api_key_configured:
            logger.error("Daimo Pay API key not configured")

        webhook_secret_configured = bool(
            self.settings.DAIMO_WEBHOOK_SECRET is not None
            and len(self.settings.DAIMO_WEBHOOK_SECRET) > 0
        )
        if not webhook_secret_configured:
            logger.error("Daimo Pay webhook secret not configured")

        return all((
            api_key_configured,
            webhook_secret_configured,
            super().is_allowed(request, **kwargs),
        ))

    def payment_form_render(self, request, total, order=None):
        form = self.payment_form(request)
        template = get_template('pretix_eth/checkout_payment_form.html')
        ctx = {'request': request, 'form': form}
        return template.render(ctx)

    def checkout_confirm_render(self, request):
        template = get_template("pretix_eth/checkout_payment_confirm.html")
        return template.render()

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        request_data = {
            "intent": f"Pretix Order #{payment.order.code}",
            "items": [{
                "description": f"Order #{payment.order.code}",
                "amount": str(payment.amount),
            }],
            "recipient": {
                "address": payment.order.email,  # TODO: Configure recipient address
                "amount": str(payment.amount),
                "token": "USDC",  # TODO: Make configurable
                "chain": "base",  # TODO: Make configurable
            },
            "redirectUri": request.build_absolute_uri(
                reverse('control:event.order', kwargs={
                    'event': payment.order.event.slug,
                    'organizer': payment.order.event.organizer.slug,
                    'code': payment.order.code
                })
            )
        }
        
        try:
            response = requests.post(
                "https://pay.daimo.com/api/generate",
                headers={
                    "Api-Key": self.settings.DAIMO_API_KEY,
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            
            data = response.json()
            if response.status_code != 200 or not data.get("id") or not data.get("url"):
                logger.error(f"Daimo Pay API error: {response.text}")
                payment.fail()
                return
            
            payment.info_data = {
                "payment_id": data["id"],
                "payment_url": data["url"],
                "amount": str(payment.amount),
                "time": int(time.time()),
            }
            payment.save(update_fields=["info"])
            
        except Exception as e:
            logger.error(f"Error in Daimo Pay API request: {str(e)}")
            payment.fail()

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/pending.html")
        ctx = RequestContext(request, {
            "payment_is_valid": True,
            "order": payment.order,
            "payment": payment,
            'event': self.event,
            "payment_url": payment.info_data.get("payment_url", "#"),
        })
        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("pretix_eth/control.html")
        ctx = {
            "payment_info": payment.info_data,
        }
        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return False

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return self.payment_refund_supported(payment)

    def execute_refund(self, refund: OrderRefund):
        raise Exception("Refunds are disabled for this payment provider.")
