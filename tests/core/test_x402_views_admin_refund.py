# tests/core/test_x402_views_admin_refund.py
import json
import pytest
from decimal import Decimal
from django_scopes import scopes_disabled
from pretix_eth.models import X402CompletedOrder


@pytest.fixture
def completed_order(event):
    with scopes_disabled():
        return X402CompletedOrder.objects.create(
            event=event, tx_hash='0x' + 'a' * 64, payment_reference='x402_refx',
            pretix_order_code='REFX', payer='0x' + '1' * 40, chain_id=8453,
            total_usd=Decimal('10.00'), token_symbol='USDC',
        )


@pytest.mark.django_db
def test_initiate_refund(api_client, event, completed_order):
    resp = api_client.post('/plugin/x402/admin/refund/?action=initiate', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_refx',
        'admin_address': '0x' + '9' * 40,
    }), content_type='application/json')
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True

    with scopes_disabled():
        o = X402CompletedOrder.objects.get(payment_reference='x402_refx')
        assert o.refund_status == 'pending'


@pytest.mark.django_db
def test_confirm_refund(api_client, event, completed_order):
    api_client.post('/plugin/x402/admin/refund/?action=initiate', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_refx',
        'admin_address': '0x' + '9' * 40,
    }), content_type='application/json')

    resp = api_client.post('/plugin/x402/admin/refund/?action=confirm', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_refx',
        'refund_tx_hash': '0x' + 'f' * 64,
    }), content_type='application/json')
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True

    with scopes_disabled():
        o = X402CompletedOrder.objects.get(payment_reference='x402_refx')
        assert o.refund_status == 'confirmed'
        assert o.refund_tx_hash == '0x' + 'f' * 64


@pytest.mark.django_db
def test_fail_refund(api_client, event, completed_order):
    api_client.post('/plugin/x402/admin/refund/?action=initiate', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_refx',
        'admin_address': '0x' + '9' * 40,
    }), content_type='application/json')

    resp = api_client.post('/plugin/x402/admin/refund/?action=fail', data=json.dumps({
        'organizer': event.organizer.slug, 'event': event.slug,
        'payment_reference': 'x402_refx',
        'error': 'out of gas',
    }), content_type='application/json')
    assert resp.status_code == 200

    with scopes_disabled():
        o = X402CompletedOrder.objects.get(payment_reference='x402_refx')
        assert o.refund_status == 'failed'
        assert 'out of gas' in o.refund_meta.get('error', '')
