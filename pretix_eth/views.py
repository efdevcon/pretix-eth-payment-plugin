import json
import hmac
import hashlib
import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import path
from django_scopes import scope

from pretix.base.models import Order, OrderPayment

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework import permissions, mixins

logger = logging.getLogger(__name__)

def verify_webhook_signature(request, secret):
    """Verify Daimo Pay webhook signature"""
    signature = request.headers.get('Authorization')
    if not signature:
        return False
        
    # Remove 'Bearer ' prefix if present
    if signature.startswith('Bearer '):
        signature = signature[7:]
        
    # Calculate expected signature
    expected = hmac.new(
        secret.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)

@csrf_exempt
@require_POST
def daimo_webhook(request, *args, **kwargs):
    """Handle Daimo Pay webhook events"""
    try:
        # Parse webhook payload
        payload = json.loads(request.body)
        event_type = payload.get('type')
        payment_id = payload.get('paymentId')
        
        if not event_type or not payment_id:
            return HttpResponseBadRequest("Missing event type or payment ID")
            
        # Find payment and its organizer
        from pretix.base.models import Organizer
        from django_scopes import scope, get_scope
        
        # Get all organizers since we can't scope the initial query
        organizers = Organizer.objects.all()
        payment = None
        
        # Try each organizer scope until we find the payment
        for organizer in organizers:
            with scope(organizer=organizer):
                try:
                    # Use proper JSON field lookup
                    payment = OrderPayment.objects.select_related(
                        'order__event__organizer'
                    ).filter(
                        info__icontains=payment_id
                    ).get()
                    break
                except OrderPayment.DoesNotExist:
                    continue
                    
        if not payment:
            return HttpResponseBadRequest("Payment not found")
            
        # Continue with the correct scope
        with scope(organizer=payment.order.event.organizer):
            # Verify webhook signature within the correct scope
            if not verify_webhook_signature(request, payment.payment_provider.settings.DAIMO_WEBHOOK_SECRET):
                return HttpResponseBadRequest("Invalid signature")
                
            # Handle payment completion
            if event_type == 'payment_completed':
                payment.confirm()
            elif event_type == 'payment_bounced':
                payment.fail()
                
            return HttpResponse(status=200)
            payment = OrderPayment.objects.select_related(
                'order__event__organizer'
            ).get(id=payment_id)
            
        # Use correct organizer scope for operations
        with scope(organizer=payment.order.event.organizer):
            # Verify webhook signature
            if not verify_webhook_signature(request, payment.payment_provider.settings.DAIMO_WEBHOOK_SECRET):
                return HttpResponseBadRequest("Invalid signature")
                
            # Handle payment completion
            if event_type == 'payment_completed':
                payment.confirm()
            elif event_type == 'payment_bounced':
                payment.fail()
                
            return HttpResponse(status=200)
            
    except (json.JSONDecodeError, KeyError) as e:
        return HttpResponseBadRequest(f"Invalid webhook payload: {str(e)}")
    except Exception as e:
        logger.exception("Error processing webhook")
        return HttpResponseBadRequest(f"Error processing webhook: {str(e)}")

# URL configuration
webhook_patterns = [
    path('webhook/', daimo_webhook, name='webhook'),
]

# URL configuration
webhook_patterns = [
    path('webhook/', daimo_webhook, name='webhook'),
]


# No views needed beyond webhook handler
