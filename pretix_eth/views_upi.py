"""Buyer-facing entry points for the UPI-via-Checkout provider (prototype):
the one-click start used by the storefront, the buyer's return from Stripe
and the Stripe webhook.

Return and webhook never trust what the browser or the webhook body says:
both re-read the Checkout Session from Stripe's API through the provider and
act on that. All routes are event-scoped (`urls._upi_routes`), so
`request.event` is set by Pretix before they run.
"""
import json
import logging

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_scopes import scopes_disabled
from pretix.base.models import Order, OrderPayment
from pretix.base.payment import PaymentException
from pretix.base.services.orders import change_payment_provider
from pretix.helpers.http import redirect_to_url
from pretix.multidomain.urlreverse import eventreverse

from pretix_eth.payment_upi import SECRET_TAG, StripeCheckoutUPI

log = logging.getLogger(__name__)


def _order_url(event, order):
    url = eventreverse(event, 'presale:event.order', kwargs={'order': order.code, 'secret': order.secret})
    return url + ('?paid=yes' if order.status == Order.STATUS_PAID else '')


def _event(request):
    event = getattr(request, 'event', None)
    if event is None:
        raise Http404('event-scoped route')
    return event


OPEN_STATES = (OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING)


@require_GET
def upi_start(request, order, secret, **kwargs):
    """One click from the storefront's order page straight to Stripe's page.

    Does what Pretix's "change payment method" page does when the buyer picks
    UPI (same checks, same `change_payment_provider` call, so fees, logs and
    invoices behave the same) and then starts the payment immediately instead
    of showing Pretix's confirm page. Anything that stops the payment sends
    the buyer to the Pretix order page with the reason as a message.
    """
    event = _event(request)
    provider = StripeCheckoutUPI(event)
    with scopes_disabled():
        try:
            order_obj = event.orders.get_with_secret_check(code=order, received_secret=secret, tag=None)
        except Order.DoesNotExist:
            raise Http404('Unknown order')
        back = _order_url(event, order_obj)

        if order_obj.status not in (Order.STATUS_PENDING, Order.STATUS_EXPIRED) or order_obj._can_be_paid() is not True:
            messages.error(request, _('The payment for this order cannot be continued.'))
            return redirect_to_url(back)
        term_last = order_obj.payment_term_last
        if term_last and now() > term_last:
            messages.error(request, _('The payment is too late to be accepted.'))
            return redirect_to_url(back)
        if not provider.is_enabled or not provider.order_change_allowed(order_obj):
            messages.error(request, _('UPI is not available for this order.'))
            return redirect_to_url(back)

        open_payment = order_obj.payments.filter(state__in=OPEN_STATES).last()
        if open_payment and open_payment.provider == provider.identifier \
                and open_payment.state == OrderPayment.PAYMENT_STATE_CREATED:
            payment = open_payment
        elif open_payment and open_payment.state == OrderPayment.PAYMENT_STATE_PENDING \
                and not open_payment.payment_provider.abort_pending_allowed:
            messages.error(request, _('A payment is currently pending for this order.'))
            return redirect_to_url(back)
        else:
            with transaction.atomic():
                payment = change_payment_provider(order_obj, provider, None)[3]
        try:
            return redirect_to_url(provider.execute_payment(request, payment))
        except PaymentException as e:
            messages.error(request, str(e))
            return redirect_to_url(back)


@require_GET
def upi_return(request, order, secret_hash, payment, **kwargs):
    """Where Stripe sends the buyer after the Checkout page (paid or cancelled)."""
    event = _event(request)
    with scopes_disabled():
        try:
            order_obj = event.orders.get_with_secret_check(
                code=order, received_secret=secret_hash.lower(), tag=SECRET_TAG,
            )
        except Order.DoesNotExist:
            raise Http404('Unknown order')
        payment_obj = get_object_or_404(order_obj.payments, pk=payment, provider=StripeCheckoutUPI.identifier)
        if not request.GET.get('cancelled'):
            try:
                StripeCheckoutUPI(event).sync_payment(payment_obj)
            except PaymentException as e:
                messages.error(request, str(e))
            except Exception:
                log.exception('[upi] return check failed for order %s', order_obj.code)
                messages.error(request, _('We could not check the payment with Stripe. Please try again in a moment.'))
        order_obj.refresh_from_db()
        return redirect_to_url(_order_url(event, order_obj))


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@csrf_exempt
@require_POST
def upi_webhook(request, **kwargs):
    """Stripe `checkout.session.*` events. The body only tells us WHICH
    payment to re-check; the session is read back from Stripe before anything
    changes, so no signing secret is needed.
    """
    event = _event(request)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse('invalid json', status=400)
    obj = ((body.get('data') or {}).get('object') or {}) if isinstance(body, dict) else {}
    if obj.get('object') != 'checkout.session':
        return HttpResponse('ignored')
    meta = obj.get('metadata') or {}
    with scopes_disabled():
        payment = OrderPayment.objects.filter(
            order__event=event, order__code=meta.get('order'), pk=_int(meta.get('payment')),
            provider=StripeCheckoutUPI.identifier,
        ).select_related('order').first()
        if payment is None:
            return HttpResponse('unknown payment')
        if (payment.info_data or {}).get('session_id') != obj.get('id'):
            return HttpResponse('session mismatch')
        try:
            StripeCheckoutUPI(event).sync_payment(payment)
        except PaymentException as e:
            # Recorded on the payment (an amount mismatch, for instance): a
            # Stripe retry would change nothing, so no 5xx.
            log.warning('[upi] webhook: %s (order %s)', e, payment.order.code)
            return HttpResponse('recorded')
        except Exception:
            log.exception('[upi] webhook check failed for order %s', payment.order.code)
            return HttpResponse('check failed', status=500)
    return HttpResponse('ok')
