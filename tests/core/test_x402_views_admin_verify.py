# tests/core/test_x402_views_admin_verify.py
import json
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django_scopes import scopes_disabled

from pretix_eth.models import X402PendingOrder, X402CompletedOrder


@pytest.fixture
def pending_for_admin_verify(event):
    with scopes_disabled():
        return X402PendingOrder.objects.create(
            event=event,
            payment_reference='x402_admin_v1',
            order_data={'email': 'a@b.c', 'tickets': [{'itemId': 1, 'quantity': 1}]},
            total_usd=Decimal('10.00'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )


@pytest.fixture
def event_with_recipient(event):
    event.settings.set('payment_walletconnect_payment_recipient', '0xA163a78C0b811A984fFe1B98b4b1b95BAb24aAcD')
    return event


@pytest.mark.django_db
def test_admin_verify_rejects_missing_pending(api_client, event_with_recipient):
    """Admin verify cannot synthesize a pending order — it's strictly a
    recovery tool for payments that already have one. This prevents an admin
    from creating a Pretix order from an arbitrary tx hash."""
    resp = api_client.post('/plugin/x402/admin/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'paymentReference': 'x402_does_not_exist',
        'txHash': '0x' + 'a' * 64,
        'payer': '0x' + '1' * 40,
        'chainId': 8453, 'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 404
    assert 'not found' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_admin_verify_rejects_bad_tx_hash(api_client, event_with_recipient, pending_for_admin_verify):
    resp = api_client.post('/plugin/x402/admin/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'paymentReference': 'x402_admin_v1',
        'txHash': 'not-a-hash',
        'payer': '0x' + '1' * 40,
        'chainId': 8453, 'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 400
    assert 'tx_hash' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_admin_verify_rejects_reused_tx_hash(api_client, event_with_recipient, pending_for_admin_verify):
    """The same tx_hash uniqueness check applies — admin endpoint cannot be
    used to attribute a tx already claimed by another order."""
    with scopes_disabled():
        X402CompletedOrder.objects.create(
            event=event_with_recipient, tx_hash='0x' + 'a' * 64,
            payment_reference='other_order', pretix_order_code='X',
            payer='0x' + '9' * 40, chain_id=8453,
            total_usd=Decimal('1'), token_symbol='USDC',
        )
    resp = api_client.post('/plugin/x402/admin/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'paymentReference': 'x402_admin_v1',
        'txHash': '0x' + 'a' * 64,
        'payer': '0x' + '1' * 40,
        'chainId': 8453, 'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 400
    assert 'already used' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_admin_verify_rejects_payer_mismatch(api_client, event_with_recipient, pending_for_admin_verify):
    """The payer the admin submits must match the intended_payer the buyer
    committed to at purchase time. Prevents an admin from retargeting a
    payment to a different wallet."""
    resp = api_client.post('/plugin/x402/admin/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'paymentReference': 'x402_admin_v1',
        'txHash': '0x' + 'b' * 64,
        'payer': '0x' + '9' * 40,  # intended_payer is 0x111...
        'chainId': 8453, 'symbol': 'USDC',
    }), content_type='application/json')
    assert resp.status_code == 403
    assert 'payer does not match' in resp.json()['error'].lower()


@pytest.mark.django_db
def test_admin_verify_bypasses_eth_signature_requirement(api_client, event_with_recipient, pending_for_admin_verify):
    """Admin manual-verify is a stuck-payment recovery path. Re-collecting an
    `ethPayerSignature` from the user is impractical at recovery time, so the
    requirement is intentionally skipped here — payer-binding falls back to
    the on-chain `tx.from == intended_payer` check enforced by
    `verify_native_eth`. Mirrors the bypass the user-facing verify endpoint
    explicitly forbids; the admin endpoint is auth-gated by the Pretix API
    token and intended for operator use only."""
    resp = api_client.post('/plugin/x402/admin/verify/', data=json.dumps({
        'organizer': event_with_recipient.organizer.slug, 'event': event_with_recipient.slug,
        'paymentReference': 'x402_admin_v1',
        'txHash': '0x' + 'c' * 64,
        'payer': '0x' + '1' * 40,
        'chainId': 1, 'symbol': 'ETH',
    }), content_type='application/json')
    # Should NOT 400 with "ethPayerSignature is required" anymore. The flow
    # proceeds past the signature gate and fails later (on-chain verify
    # against a fake tx, etc.) — we just assert the signature gate didn't
    # short-circuit.
    body = resp.json()
    err = (body.get('error') or '').lower()
    assert 'ethpayersignature' not in err.replace(' ', ''), \
        f'admin verify should bypass ethPayerSignature requirement; got: {body}'
