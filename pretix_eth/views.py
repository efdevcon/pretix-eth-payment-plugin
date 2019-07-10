import hashlib
import json
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pretix.base.models import Order, Quota, OrderPayment
from pretix.base.services.locking import LockTimeoutException
from pretix.base.settings import GlobalSettingsObject
from pretix.control.permissions import event_permission_required
from pretix.multidomain.urlreverse import eventreverse
from .models import ReferencedEthereumObject
from .payment import Ethereum
from .txn_check import check_txn_confirmation

logger = logging.getLogger(__name__)

#def pending(request, payment):
 #   template = loader.get_template('pretix_eth/pending.html')
  #  ctx = {'request': request, 'event': self.event, 'settings': self.settings,
   #             'order': payment.order, 'provname': self.verbose_name, 'amount': payment.amount}
   # return HttpResponse(template.render(ctx, request))

def pending(request, *args, **kwargs):
    url = request.GET.get('url', '')
    r = render(request, 'pretix_eth/pending.html', {
        'url': url,
    })
    r._csp_ignore = True
    return r

@xframe_options_exempt
def redirect_view(request, *args, **kwargs):
    signer = signing.Signer(salt='safe-redirect')
    try:
        url = signer.unsign(request.GET.get('url', ''))
    except signing.BadSignature:
        return HttpResponseBadRequest('Invalid parameter')

    r = render(request, 'pretix_eth/redirect.html', {
        'url': url,
    })
    r._csp_ignore = True
    return r

def process_invoice(order, payment, invoice_id, request, *args, **kwargs):
    prov = Ethereum(order.event)
    src = prov.client.get_invoice(invoice_id)

    if not payment:
        payment = order.payments.filter(
            info__icontains=invoice_id,
            provider='Ethereum',
        ).last()
    if not payment:
        payment = order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CREATED,
            provider='Ethereum',
            amount=Decimal(src['amount']),
            info=json.dumps(src),
        )

    with transaction.atomic():
        order.refresh_from_db()
        payment.refresh_from_db()

        if src['status'] == 'new':
            pass
        elif src['status'] in ('paid', 'confirmed', 'complete'):
            if payment.state in (OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING):   
                txn_hash = request.session['fm_txn_hash']
                from_address = request.session['fm_address']
                currency = request.session['fm_currency']
                amount = request.session['amount']
                to_address = self.settings.ETH if (currency == 'ETH') else self.settings.DAI
                if check_txn_confirmation(txn_hash, from_address, to_address, currency, amount):
                    try:
                         payment.confirm()
                    except LockTimeoutException:
                        return HttpResponse("Lock timeout, please try again.", status=503)
                    except Quota.QuotaExceededException:
                        return HttpResponse("Quota exceeded.", status=200)
                r = render(request, 'pretix_eth/pending.html')
                return r
        elif src['status'] == ('expired', 'invalid'):
            if payment.state in (OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING):
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.info = json.dumps(src)
                payment.save()
            elif order.state in OrderPayment.PAYMENT_STATE_CONFIRMED:
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.info = json.dumps(src)
                payment.save()

    return HttpResponse(status=200)

@event_permission_required('can_change_event_settings')
def auth_start(request, **kwargs):
    if request.event.settings.payment_ethereum_token:
        messages.error(request, _('You are already connected to this ethereum core.'))
        return redirect(reverse('control:event.settings.payment.provider', kwargs={
            'organizer': request.event.organizer.slug,
            'event': request.event.slug
        }))
    request.session['payment_ethereum_auth_event'] = request.event.pk
    pem = request.event.settings.payment_ethereum_pem
    if not pem:
        gs = GlobalSettingsObject()
        pem = gs.settings.payment_ethereum_pem = key_utils.generate_pem()

    sin = key_utils.get_sin_from_pem(pem)
    if request.GET.get('url'):
        url = request.GET.get('url')
    else:
        url = 'https://localhost/not_implemented' if 'test' in request.GET else 'https://localhost'
    try:
        r = requests.post(
            url + '/tokens',
            json={
                'label': settings.PRETIX_INSTANCE_NAME,
                'facade': 'merchant',
                'id': sin
            }
        )
    except requests.ConnectionError:
        messages.error(request, _('Communication with Ethereum was not successful.'))
    else:
        if r.status_code == 200:
            data = r.json()['data'][0]
            request.event.settings.payment_ethereum_token = data['token']
            request.event.settings.payment_ethereum_url = url
            return redirect(
                url + '/api-access-request?pairingCode=' + data['pairingCode']
            )
        messages.error(request, _('Communication with Ethereum core was not successful.'))

    return redirect(reverse('control:event.settings.payment.provider', kwargs={
        'organizer': request.event.organizer.slug,
        'event': request.event.slug
}))


