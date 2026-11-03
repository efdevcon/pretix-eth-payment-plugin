"""Buyer return and Stripe webhook for the UPI-via-Checkout provider (prototype).

Neither view trusts what the browser or the webhook body says: both re-read
the Checkout Session from Stripe's API through the provider and act on that.
Both routes are event-scoped (`urls._upi_routes`), so `request.event` is set
by Pretix before they run.
"""
import json
import logging

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_scopes import scopes_disabled
from pretix.base.models import Order, OrderPayment
from pretix.base.payment import PaymentException
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
        except Exception:
            log.exception('[upi] webhook check failed for order %s', payment.order.code)
            return HttpResponse('check failed', status=500)
    return HttpResponse('ok')
