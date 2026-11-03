"""UPI via Stripe Checkout (prototype).

Each product that may be paid by UPI carries a rupee price in the item meta
property `upi_price_inr` (Items > Edit > Metadata). The rupee prices of the
main products in an order set the order's exchange rate, so vouchers, add-ons
without a rupee price and payment fees are converted at that same rate. The
Checkout Session is created in INR for that amount and limited to UPI;
Pretix keeps recording the order in the event currency, and Stripe converts
the rupees to the account's settlement currency at payout (that conversion
fee is on the business, not the buyer).

Flow: the buyer picks "UPI" in checkout; once the order is placed,
`execute_payment` creates a Checkout Session and redirects to it. Stripe
sends the buyer back to `views_upi.upi_return`, which re-reads the session
from the API and confirms the payment when it is paid. The optional webhook
(`views_upi.upi_webhook`) does the same for buyers who closed the tab, and
the order page links to the same return URL as a "check the payment status"
action (no Stripe call while rendering, so an outage cannot stall the page).
A storefront can start the payment in one click through `views_upi.upi_start`.

Needs, on the Stripe account: UPI enabled, and INR accepted as a presentment
currency. The API version is pinned per request because the Stripe plugin
shipped with Pretix pins the process-wide `stripe.api_version` to a release
that predates `allowed_payment_method_types`.
"""
import logging
import time
from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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
PAID_STATUSES = ('paid', 'no_payment_required')
UPI_PRICE_META = 'upi_price_inr'   # item meta property: the product's rupee price
UPI_CURRENCY = 'INR'
# The session is in rupees, so UPI alone is a valid filter; card buyers use
# the Stripe plugin's own rail.
DEFAULT_METHODS = 'upi'
PLACES = Decimal('0.01')


def _split_methods(value):
    return [m.strip() for m in str(value or '').split(',') if m.strip()]


def _minor_units(currency: str, amount: Decimal) -> int:
    places = dj_settings.CURRENCY_PLACES.get(currency.upper(), 2)
    return int((Decimal(amount) * (10 ** places)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _positive_decimal(value):
    """A rupee price or card price from item metadata; None when unset or unusable."""
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None
    return d if d > 0 else None


def _fiat_list_price(position):
    """The event-currency list price a product's rupee price is paired with:
    the card price override when the product has one, else the product's (or
    variation's) own price."""
    override = _positive_decimal(position.item.meta_data.get('fiat_price_usd'))
    if override is not None:
        return override
    if position.variation_id and position.variation.default_price is not None:
        return Decimal(position.variation.default_price)
    return Decimal(position.item.default_price or 0)


def inr_rate(positions):
    """Rupees per unit of the event currency, implied by the rupee prices of
    the main products among `positions` (cart or order positions).

    Every charged main product needs a rupee price, or UPI is not offered:
    the rail is an allow-list and the rupee price is the switch. Add-ons
    follow their parent and free positions carry no rate. None when nothing
    is priced.
    """
    inr_sum = usd_sum = Decimal('0')
    for pos in positions:
        if pos.addon_to_id is not None or Decimal(pos.price or 0) <= 0:
            continue
        inr = _positive_decimal(pos.item.meta_data.get(UPI_PRICE_META))
        if inr is None:
            return None
        usd = _fiat_list_price(pos)
        if usd <= 0:
            return None
        inr_sum += inr
        usd_sum += usd
    return (inr_sum / usd_sum) if usd_sum > 0 else None


def inr_amount(amount, rate) -> Decimal:
    return (Decimal(amount) * Decimal(rate)).quantize(PLACES, rounding=ROUND_HALF_UP)


def _presentment(session, event_currency):
    """What the buyer was charged, as Stripe minor units plus currency: the
    session's own amount when it was created in another currency than the
    event's (the rupee session), else Adaptive Pricing's `presentment_details`
    from older sessions."""
    currency = (session.get('currency') or '').lower() if hasattr(session, 'get') else ''
    if currency and currency != event_currency.lower():
        return {'amount': session.get('amount_total'), 'currency': currency}
    details = session.get('presentment_details') if hasattr(session, 'get') else None
    if not details:
        return None
    return {
        'amount': details.get('presentment_amount'),
        'currency': details.get('presentment_currency'),
    }


def _presentment_parts(info):
    """What Stripe charged the buyer, as ('2250.00', 'INR'); (None, None) when
    the session was never paid."""
    pres = (info or {}).get('presentment') or {}
    amount, currency = pres.get('amount'), pres.get('currency')
    if amount is None or not currency:
        return None, None
    places = dj_settings.CURRENCY_PLACES.get(currency.upper(), 2)
    return f'{Decimal(amount) / (10 ** places):.{places}f}', currency.upper()


def _format_presentment(info) -> str:
    amount, currency = _presentment_parts(info)
    return f'{amount} {currency}' if amount else ''


class StripeCheckoutUPI(BasePaymentProvider):
    identifier = 'stripe_checkout_upi'
    verbose_name = _('UPI via Stripe Checkout')
    public_name = _('UPI via Stripe (Google Pay, PhonePe, Paytm, BHIM)')
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
            initial=DEFAULT_METHODS,
            help_text=_('Comma-separated Stripe method types for the rupee session, "upi" by default. '
                        'Empty shows everything enabled for INR in the Stripe dashboard (cards included). '
                        'UPI is offered only for products with a rupee price in the item meta property '
                        '"upi_price_inr"; that price also sets the rate for vouchers, fees and add-ons.'),
        )
        return fields

    # ----- configuration ---------------------------------------------------

    def api_key(self) -> str:
        return self.settings.get('secret_key') or self.event.settings.get('payment_stripe_secret_key') or ''

    def allowed_methods(self):
        raw = self.settings.get('payment_methods', default=DEFAULT_METHODS)
        if raw is None:
            raw = DEFAULT_METHODS
        return _split_methods(raw)

    def _stripe_kwargs(self):
        return {'api_key': self.api_key(), 'stripe_version': STRIPE_API_VERSION}

    def is_allowed(self, request, total=None):
        if not self.api_key() or not super().is_allowed(request, total):
            return False
        from pretix_eth.apps import _cart_or_order_positions
        return inr_rate(_cart_or_order_positions(self.event, request)) is not None

    def order_change_allowed(self, order, request=None):
        if not self.api_key() or not super().order_change_allowed(order, request=request):
            return False
        return self.order_rate(order) is not None

    def order_rate(self, order):
        return inr_rate(order.positions.select_related('item', 'variation'))

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

    def quote(self, payment):
        """(rate, rupee amount) for this payment, from the order's products."""
        rate = self.order_rate(payment.order)
        if rate is None:
            raise PaymentException(_('This order has no rupee price, so it cannot be paid by UPI.'))
        return rate, inr_amount(payment.amount, rate)

    def create_session(self, payment, rupees):
        import stripe
        order = payment.order
        return_url = self._return_url(payment)
        kwargs = {
            'mode': 'payment',
            'line_items': [{
                'quantity': 1,
                'price_data': {
                    'currency': UPI_CURRENCY.lower(),
                    'unit_amount': _minor_units(UPI_CURRENCY, rupees),
                    'product_data': {'name': f'{self.event.name}: order {order.code}'},
                },
            }],
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
        except stripe.error.InvalidRequestError as e:
            # A 400 is our configuration or Stripe's account setup, not an outage:
            # retrying will not help the buyer, support has to look at the log.
            log.exception('[upi] Checkout Session create rejected for order %s: %s', order.code, e)
            raise PaymentException(_('Stripe rejected the payment setup for this order. Please contact support.'))
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
        rate, rupees = self.quote(payment)
        session = self.create_session(payment, rupees)
        payment.info_data = {
            'session_id': session.id,
            'session_url': session.url,
            'expires_at': session.expires_at,
            'session_status': session.status,
            'payment_status': session.payment_status,
            'amount': str(payment.amount),
            'currency': UPI_CURRENCY,
            'inr_amount': str(rupees),
            'inr_rate': str(rate.quantize(Decimal('0.000001'))),
        }
        payment.state = OrderPayment.PAYMENT_STATE_CREATED
        payment.save(update_fields=['info', 'state'])
        return session.url

    def _charged(self, payment):
        """(currency, amount) the session was created for: rupees, or the event
        currency for sessions from before the rupee prices."""
        info = payment.info_data or {}
        if info.get('inr_amount'):
            return UPI_CURRENCY, Decimal(info['inr_amount'])
        return self.event.currency, Decimal(str(payment.amount))

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
            'presentment': _presentment(session, self.event.currency),
            'checked_at': int(time.time()),
        })
        if session.payment_status in PAID_STATUSES:
            if payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
                return
            currency, amount = self._charged(payment)
            expected = _minor_units(currency, amount)
            got, got_currency = int(session.get('amount_total') or 0), (session.get('currency') or '').lower()
            payment.info_data = info
            payment.save(update_fields=['info'])
            if got != expected or got_currency != currency.lower():
                log.error('[upi] amount mismatch on order %s: Stripe says %s %s, payment expects %s %s',
                          payment.order.code, got, got_currency, expected, currency.lower())
                raise PaymentException(_('Stripe reported a different amount than this order. Please contact support.'))
            try:
                # The recap is passed explicitly: the plugin's confirm() wrapper
                # would otherwise build it while the payment still reads "created".
                payment.confirm(mail_text='\n\n'.join(self._paid_recap_lines(payment)))
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
        pay_url = check_url = None
        if payment.state in open_states and info.get('session_id'):
            # No Stripe call while rendering: an outage would stall every pending
            # order page. A buyer who paid and closed the Stripe tab re-checks
            # through the return URL, which re-reads the session and confirms.
            check_url = self._return_url(payment)
            still_open = info.get('session_status') == 'open' and int(info.get('expires_at') or 0) > time.time()
            if still_open and info.get('session_url'):
                pay_url = info['session_url']
        return get_template('pretix_eth/upi_pending.html').render({'pay_url': pay_url, 'check_url': check_url})

    def payment_control_render(self, request, payment):
        info = payment.info_data or {}
        intent = info.get('payment_intent')
        return get_template('pretix_eth/upi_control.html').render({
            'info': info,
            'presentment': _format_presentment(info),
            'dashboard_url': f'https://dashboard.stripe.com/payments/{intent}' if intent else None,
        })

    def _is_paid(self, payment) -> bool:
        """Confirmed, or about to be: `apply_session` saves Stripe's "paid"
        answer before `confirm()`, and the mail text is built inside it."""
        return payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED \
            or (payment.info_data or {}).get('payment_status') in PAID_STATUSES

    def _paid_recap_lines(self, payment):
        from pretix.base.templatetags.money import money_filter
        info = payment.info_data or {}
        lines = [
            str(_('Payment method: UPI via Stripe')),
            str(_('Amount: {amount}')).format(amount=money_filter(Decimal(str(payment.amount)), self.event.currency)),
        ]
        charged = _format_presentment(info)
        if charged:
            lines.append(str(_('Charged to you as: {amount}')).format(amount=charged))
        if info.get('payment_intent'):
            lines.append(str(_('Stripe reference: {ref}')).format(ref=info['payment_intent']))
        return lines

    def order_pending_mail_render(self, order, payment) -> str:
        # The plugin also fills {payment_info} of the "payment received" email
        # from this text (apps._install_payment_info_autofill), so it follows
        # the payment's state: a recap once paid, instructions before.
        if self._is_paid(payment):
            return '\n\n'.join(self._paid_recap_lines(payment))
        return str(_('Open your order page and choose "Continue with UPI" to complete the payment.'))

    def render_invoice_text(self, order, payment) -> str:
        text = str(super().render_invoice_text(order, payment))
        charged = _format_presentment(payment.info_data) if self._is_paid(payment) else ''
        if charged:
            text = '{} {}'.format(text, _('Paid by UPI via Stripe, charged as {amount}.').format(amount=charged)).strip()
        return text

    def api_payment_details(self, payment):
        info = payment.info_data or {}
        amount, currency = _presentment_parts(info)
        return {
            'session_id': info.get('session_id'),
            'payment_intent': info.get('payment_intent'),
            'presentment_amount': amount,
            'presentment_currency': currency,
        }

    def matching_id(self, payment):
        return (payment.info_data or {}).get('payment_intent')

    # ----- refunds -----------------------------------------------------------

    def payment_refund_supported(self, payment):
        return bool((payment.info_data or {}).get('payment_intent'))

    def payment_partial_refund_supported(self, payment):
        return self.payment_refund_supported(payment)

    def refund_minor_units(self, refund) -> int:
        """The refund in the session's currency: the whole charge for a full
        refund, else the same share of the rupees as of the event-currency amount."""
        currency, charged = self._charged(refund.payment)
        paid = Decimal(str(refund.payment.amount))
        if Decimal(refund.amount) >= paid:
            return _minor_units(currency, charged)
        return _minor_units(currency, (charged * Decimal(refund.amount) / paid).quantize(PLACES, rounding=ROUND_HALF_UP))

    def execute_refund(self, refund):
        import stripe
        intent = (refund.payment.info_data or {}).get('payment_intent')
        if not intent:
            raise PaymentException(_('No Stripe payment is attached to this payment.'))
        try:
            result = stripe.Refund.create(
                payment_intent=intent,
                amount=self.refund_minor_units(refund),
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
