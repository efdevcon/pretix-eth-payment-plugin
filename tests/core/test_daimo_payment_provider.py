import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
import pytest
import time

from pretix.base.models import OrderPayment

@pytest.mark.django_db
def test_provider_properties(provider):
    assert provider.identifier == "daimo_pay"
    assert provider.verbose_name == "Daimo Pay"
    assert provider.public_name == "Daimo Pay"

@pytest.mark.django_db
def test_provider_settings_form_fields(provider):
    form_fields = provider.settings_form_fields
    assert "DAIMO_API_KEY" in form_fields
    assert "DAIMO_WEBHOOK_SECRET" in form_fields

@pytest.mark.django_db
def test_provider_is_allowed(event, provider):
    factory = RequestFactory()
    session = SessionStore()
    session.create()
    request = factory.get("/checkout")
    request.event = event
    request.session = session

    # Test without required settings
    assert not provider.is_allowed(request)

    # Test with required settings
    provider.settings.set("DAIMO_API_KEY", "test_api_key")
    provider.settings.set("DAIMO_WEBHOOK_SECRET", "test_webhook_secret")
    assert provider.is_allowed(request)

@pytest.mark.django_db
def test_execute_payment_success(provider, get_order_and_payment):
    order, payment = get_order_and_payment()
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "test_payment_id",
        "url": "https://pay.daimo.com/i/test_payment_id"
    }
    
    with patch('requests.post', return_value=mock_response) as mock_post:
        factory = RequestFactory()
        request = factory.get("/checkout")
        setattr(request, 'event', provider.event)
        
        provider.settings.set("DAIMO_API_KEY", "test_api_key")
        provider.execute_payment(request, payment)
        
        # Verify API call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://pay.daimo.com/api/generate"
        assert kwargs["headers"]["Api-Key"] == "test_api_key"
        
        # Verify payment info saved
        payment.refresh_from_db()
        assert payment.info_data["payment_id"] == "test_payment_id"
        assert payment.info_data["payment_url"] == "https://pay.daimo.com/i/test_payment_id"
        assert "time" in payment.info_data
        assert payment.info_data["amount"] == str(payment.amount)

@pytest.mark.django_db
def test_execute_payment_api_error(provider, get_order_and_payment):
    order, payment = get_order_and_payment()
    
    with patch('requests.post', side_effect=Exception("API Error")):
        factory = RequestFactory()
        request = factory.get("/checkout")
        setattr(request, 'event', provider.event)
        
        provider.settings.set("DAIMO_API_KEY", "test_api_key")
        provider.execute_payment(request, payment)
        
        # Verify payment failed
        payment.refresh_from_db()
        assert payment.state == OrderPayment.PAYMENT_STATE_FAILED

@pytest.mark.django_db
def test_webhook_verify_signature():
    from pretix_eth.views import verify_webhook_signature
    
    # Create mock request with signature
    factory = RequestFactory()
    webhook_secret = "test_webhook_secret"
    payload = {"type": "payment_completed", "paymentId": "test123"}
    payload_bytes = json.dumps(payload).encode()
    
    # Calculate correct signature
    signature = hmac.new(
        webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Test valid signature
    request = factory.post(
        "/webhook/",
        data=payload_bytes,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {signature}"
    )
    assert verify_webhook_signature(request, webhook_secret)
    
    # Test invalid signature
    request = factory.post(
        "/webhook/",
        data=payload_bytes,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer invalid"
    )
    assert not verify_webhook_signature(request, webhook_secret)

@pytest.mark.django_db
def test_webhook_payment_handling(provider, get_order_and_payment):
    from pretix_eth.views import daimo_webhook
    
    order, payment = get_order_and_payment()
    payment.info_data = {
        "payment_id": "test_payment_id",
        "time": int(time.time())
    }
    payment.save()
    
    # Set webhook secret
    webhook_secret = "test_webhook_secret"
    payment.payment_provider.settings.set("DAIMO_WEBHOOK_SECRET", webhook_secret)
    
    # Test payment_completed
    payload = {
        "type": "payment_completed",
        "paymentId": "test_payment_id"
    }
    payload_bytes = json.dumps(payload).encode()
    
    signature = hmac.new(
        webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    factory = RequestFactory()
    request = factory.post(
        "/webhook/",
        data=payload_bytes,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {signature}"
    )
    
    response = daimo_webhook(request)
    assert response.status_code == 200
    
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED
    
    order.refresh_from_db()
    assert order.status == order.STATUS_PAID
