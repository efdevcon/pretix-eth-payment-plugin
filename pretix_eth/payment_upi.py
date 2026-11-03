"""UPI via Stripe Checkout (prototype).

Stripe's hosted Checkout page with Adaptive Pricing shows a buyer in India
the order in rupees and offers UPI. The Checkout Session itself is created
in the event currency, so Pretix records, refunds and reports the usual
amount; Stripe keeps the rupee figure in the session's `presentment_details`.

Flow: the buyer picks "UPI" in checkout; once the order is placed,
`execute_payment` creates a Checkout Session and redirects to it. Stripe
sends the buyer back to `views_upi.upi_return`, which re-reads the session
from the API and confirms the payment when it is paid. The optional webhook
(`views_upi.upi_webhook`) does the same for buyers who closed the tab, and
the order page re-checks an open session when it renders.

Needs, on the Stripe account: UPI enabled, Adaptive Pricing enabled, and
the event currency among the settlement currencies. The API version is
pinned per request because the Stripe plugin shipped with Pretix pins the
process-wide `stripe.api_version` to a release that predates
`adaptive_pricing` and `allowed_payment_method_types`.
"""
import logging
import time
from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.conf import settings as dj_settings
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from pretix.base.models import OrderPayment, Quota
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.multidomain.urlreverse import build_absolute_uri, eventreverse

log = logging.getLogger(__name__)

SECRET_TAG = 'plugins:pretix_eth:upi'
STRIPE_API_VERSION = '2026-10-28.endive'
SESSION_TTL = 35 * 60      # Stripe requires `expires_at` at least 30 minutes after creation
RECHECK_INTERVAL = 30      # seconds between order-page re-reads of an open session
PAID_STATUSES = ('paid', 'no_payment_required')


def _minor_units(event, amount: Decimal) -> int:
    places = dj_settings.CURRENCY_PLACES.get(event.currency, 2)
    return int((Decimal(amount) * (10 ** places)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _presentment(session):
    details = session.get('presentment_details') if hasattr(session, 'get') else None
    if not details:
        return None
    return {
        'amount': details.get('presentment_amount'),
        'currency': details.get('presentment_currency'),
    }


def _format_presentment(info) -> str:
    pres = (info or {}).get('presentment') or {}
    amount, currency = pres.get('amount'), pres.get('currency')
    if amount is None or not currency:
        return ''
    places = dj_settings.CURRENCY_PLACES.get(currency.upper(), 2)
    return f'{Decimal(amount) / (10 ** places):.{places}f} {currency.upper()}'


class StripeCheckoutUPI(BasePaymentProvider):
    identifier = 'stripe_checkout_upi'
    verbose_name = _('UPI via Stripe Checkout')
    public_name = _('UPI')
    abort_pending_allowed = True
    execute_payment_needs_user = True

    @property
    def settings_form_fields(self):
        fields = OrderedDict(list(super().settings_form_fields.items()))
        fields['secret_key'] = forms.CharField(
            label=_('Stripe secret key'),
            required=False,
            help_text=_('Leave empty to use the key configured in the Stripe plugin of this event.'),
        )
        fields['payment_methods'] = forms.CharField(
            label=_('Payment methods on the Stripe page'),
            required=False,
            initial='upi',
            help_text=_('Comma-separated Stripe method types, for example "upi" or "upi,card". '
                        'Empty shows everything enabled in the Stripe dashboard.'),
        )
        return fields

    # ----- configuration ---------------------------------------------------

    def api_key(self) -> str:
        return self.settings.get('secret_key') or self.event.settings.get('payment_stripe_secret_key') or ''

    def allowed_methods(self):
        raw = self.settings.get('payment_methods', default='upi')
        if raw is None:
            raw = 'upi'
        return [m.strip() for m in str(raw).split(',') if m.strip()]

    def _stripe_kwargs(self):
        return {'api_key': self.api_key(), 'stripe_version': STRIPE_API_VERSION}

    def is_allowed(self, request, total=None):
        return bool(self.api_key()) and super().is_allowed(request, total)

    def order_change_allowed(self, order, request=None):
        return bool(self.api_key()) and super().order_change_allowed(order, request=request)

    # ----- checkout screens --------------------------------------------------

    def payment_form_render(self, request, total=None, order=None):
        return get_template('pretix_eth/upi_form.html').render({})

    def checkout_prepare(self, request, cart):
        return True

    def payment_is_valid_session(self, request):
        return True

    def checkout_confirm_render(self, request, order=None, info_data=None):
        return get_template('pretix_eth/upi_confirm.html').render({})

    # ----- Stripe calls ------------------------------------------------------

    def _metadata(self, payment):
        return {
            'organizer': self.event.organizer.slug,
            'event': self.event.slug,
            'order': payment.order.code,
            'payment': str(payment.pk),
        }

    def _return_url(self, payment):
        order = payment.order
        return build_absolute_uri(self.event, 'plugins:pretix_eth:upi_return', kwargs={
            'order': order.code,
            'secret_hash': order.tagged_secret(SECRET_TAG),
            'payment': payment.pk,
        })

    def _order_url(self, order):
        return eventreverse(self.event, 'presale:event.order', kwargs={'order': order.code, 'secret': order.secret})

    def create_session(self, payment):
        import stripe
        order = payment.order
        return_url = self._return_url(payment)
        kwargs = {
            'mode': 'payment',
            'line_items': [{
                'quantity': 1,
                'price_data': {
                    'currency': self.event.currency.lower(),
                    'unit_amount': _minor_units(self.event, payment.amount),
                    'product_data': {'name': f'{self.event.name}: order {order.code}'},
                },
            }],
            'adaptive_pricing': {'enabled': True},
            'client_reference_id': order.code,
            'metadata': self._metadata(payment),
            'payment_intent_data': {
                'description': f'{self.event.slug} order {order.code}',
                'metadata': self._metadata(payment),
            },
            'success_url': return_url + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': return_url + '?cancelled=1',
            'expires_at': int(time.time()) + SESSION_TTL,
        }
        if order.email:
            kwargs['customer_email'] = order.email
        methods = self.allowed_methods()
        if methods:
            kwargs['allowed_payment_method_types'] = methods
        try:
            return stripe.checkout.Session.create(**kwargs, **self._stripe_kwargs())
        except stripe.error.StripeError as e:
            log.exception('[upi] Checkout Session create failed for order %s: %s', order.code, e)
            raise PaymentException(_('We had trouble reaching Stripe. Please try again in a moment.'))

    def retrieve_session(self, session_id):
        import stripe
        try:
            return stripe.checkout.Session.retrieve(session_id, **self._stripe_kwargs())
        except stripe.error.StripeError as e:
            log.exception('[upi] Checkout Session retrieve failed for %s: %s', session_id, e)
            raise PaymentException(_('We could not check the payment with Stripe. Please try again in a moment.'))

    def execute_payment(self, request, payment):
        info = payment.info_data or {}
        if info.get('session_id'):
            session = self.retrieve_session(info['session_id'])
            if session.payment_status in PAID_STATUSES:
                self.apply_session(payment, session)
                return self._order_url(payment.order)
            if session.status == 'open':
                return session.url
            # Expired, or completed without a payment: start a fresh session below.
        session = self.create_session(payment)
        payment.info_data = {
            'session_id': session.id,
            'session_url': session.url,
            'expires_at': session.expires_at,
            'session_status': session.status,
            'payment_status': session.payment_status,
            'amount': str(payment.amount),
            'currency': self.event.currency,
        }
        payment.state = OrderPayment.PAYMENT_STATE_CREATED
        payment.save(update_fields=['info', 'state'])
        return session.url

    def apply_session(self, payment, session):
        """Move the payment along to match what Stripe says about its session.
        Only the session read back from Stripe's API is trusted; callers must
        never pass in a session built from a webhook body or a query string.
        """
        info = dict(payment.info_data or {})
        intent = session.get('payment_intent')
        info.update({
            'session_status': session.status,
            'payment_status': session.payment_status,
            'payment_intent': intent if isinstance(intent, str) else getattr(intent, 'id', None),
            'presentment': _presentment(session),
            'checked_at': int(time.time()),
        })
        if session.payment_status in PAID_STATUSES:
            if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
                return
            expected = _minor_units(self.event, payment.amount)
            got, currency = int(session.get('amount_total') or 0), (session.get('currency') or '').lower()
            payment.info_data = info
            payment.save(update_fields=['info'])
            if got != expected or currency != self.event.currency.lower():
                log.error('[upi] amount mismatch on order %s: Stripe says %s %s, order needs %s %s',
                          payment.order.code, got, currency, expected, self.event.currency.lower())
                raise PaymentException(_('Stripe reported a different amount than this order. Please contact support.'))
            try:
                payment.confirm()
            except Quota.QuotaExceededException as e:
                raise PaymentException(str(e))
            payment.refresh_from_db()
            return
        if session.status == 'expired':
            if payment.state in (OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING):
                payment.fail(info=info)
                payment.refresh_from_db()
            return
        payment.info_data = info
        payment.save(update_fields=['info'])

    def sync_payment(self, payment):
        """Re-read the payment's Checkout Session from Stripe and apply it."""
        info = payment.info_data or {}
        if not info.get('session_id'):
            raise PaymentException(_('No Stripe session is attached to this payment.'))
        session = self.retrieve_session(info['session_id'])
        self.apply_session(payment, session)
        return session

    # ----- order page / backend ----------------------------------------------

    def payment_pending_render(self, request, payment):
        info = payment.info_data or {}
        open_states = (OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING)
        pay_url = None
        if payment.state in open_states and info.get('session_id'):
            # A buyer who paid and closed the Stripe tab never hit the return
            # URL; re-reading here keeps the order page right without the webhook.
            if time.time() - int(info.get('checked_at') or 0) > RECHECK_INTERVAL:
                try:
                    self.sync_payment(payment)
                    info = payment.info_data or {}
                except Exception as e:
                    log.warning('[upi] re-check failed for order %s: %s', payment.order.code, e)
            if payment.state in open_states and info.get('session_status') == 'open' and info.get('session_url'):
                pay_url = info['session_url']
        return get_template('pretix_eth/upi_pending.html').render({'pay_url': pay_url, 'payment': payment})

    def payment_control_render(self, request, payment):
        info = payment.info_data or {}
        intent = info.get('payment_intent')
        return get_template('pretix_eth/upi_control.html').render({
            'info': info,
            'presentment': _format_presentment(info),
            'dashboard_url': f'https://dashboard.stripe.com/payments/{intent}' if intent else None,
        })

    def order_pending_mail_render(self, order, payment) -> str:
        return str(_('Open your order page and choose "Continue with UPI" to complete the payment.'))

    def matching_id(self, payment):
        return (payment.info_data or {}).get('payment_intent')

    # ----- refunds -----------------------------------------------------------

    def payment_refund_supported(self, payment):
        return bool((payment.info_data or {}).get('payment_intent'))

    def payment_partial_refund_supported(self, payment):
        return self.payment_refund_supported(payment)

    def execute_refund(self, refund):
        import stripe
        intent = (refund.payment.info_data or {}).get('payment_intent')
        if not intent:
            raise PaymentException(_('No Stripe payment is attached to this payment.'))
        try:
            result = stripe.Refund.create(
                payment_intent=intent,
                amount=_minor_units(self.event, refund.amount),
                metadata={'order': refund.order.code, 'refund': str(refund.pk)},
                **self._stripe_kwargs(),
            )
        except stripe.error.StripeError as e:
            log.exception('[upi] refund failed for order %s: %s', refund.order.code, e)
            raise PaymentException(_('Stripe refused the refund: %s') % (getattr(e, 'user_message', '') or str(e)))
        refund.info_data = {'refund_id': result.id, 'status': result.status}
        refund.save(update_fields=['info'])
        if result.status == 'failed':
            raise PaymentException(_('Stripe reported the refund as failed.'))
        # UPI refunds settle asynchronously (Stripe: up to 7 working days); "pending" is the normal answer.
        refund.done()
