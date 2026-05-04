# tests/core/test_x402_views_admin_orders.py
import pytest
from decimal import Decimal
from django_scopes import scopes_disabled
from pretix_eth.models import X402CompletedOrder, X402PendingOrder


@pytest.mark.django_db
def test_admin_orders_lists_all(api_client, event):
    with scopes_disabled():
        X402CompletedOrder.objects.create(
            event=event, tx_hash='0x' + 'a' * 64, payment_reference='x402_a1',
            pretix_order_code='A1', payer='0x' + '1' * 40, chain_id=8453,
            total_usd=Decimal('10.00'), token_symbol='USDC',
        )
        X402CompletedOrder.objects.create(
            event=event, tx_hash='0x' + 'b' * 64, payment_reference='x402_a2',
            pretix_order_code='A2', payer='0x' + '2' * 40, chain_id=10,
            total_usd=Decimal('20.00'), token_symbol='USDT0',
        )

    resp = api_client.get(
        f'/plugin/x402/admin/orders/?organizer={event.organizer.slug}&event={event.slug}',
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert len(body['completed']) == 2
    # camelCase contract (devcon admin UI reads these names directly)
    row = body['completed'][0]
    for k in ('source', 'paymentReference', 'txHash', 'pretixOrderCode', 'payer',
              'completedAt', 'chainId', 'totalUsd', 'tokenSymbol',
              'cryptoAmount', 'gasCostWei'):
        assert k in row, f'missing key: {k}'
    assert row['source'] == 'x402'
    assert 'origin' not in row  # origin column was removed from the admin UI
    # completedAt is unix-seconds, not ISO — admin UI multiplies by 1000
    assert isinstance(row['completedAt'], int)
    assert row['completedAt'] > 0
    # stats rollup — totalUsd counts only x402 rows (we have decimal totals for them)
    assert body['stats']['completed'] == 2
    assert body['stats']['x402Count'] == 2
    assert body['stats']['legacyCount'] == 0
    assert body['stats']['pending'] == 0
    assert body['stats']['totalUsd'] == '30.00'


@pytest.mark.django_db
def test_admin_orders_pending_row_shape(api_client, event):
    """Pending rows must carry camelCase keys + unix-seconds timestamps + a
    `metadata` bag rich enough for the admin table (ticketIds, addonIds, voucher)."""
    from django.utils import timezone
    from datetime import timedelta
    with scopes_disabled():
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_p_shape', total_usd=Decimal('42.00'),
            expires_at=timezone.now() + timedelta(hours=1),
            intended_payer='0x' + 'f' * 40,
            expected_chain_id=10,
            order_data={
                'email': 'pending@x.com',
                'tickets': [],
                'addons': [{'item': {'id': 17}, 'quantity': 1}, {'item': {'id': 18}}],
                'voucher': 'VOUCHER123',
            },
            metadata={'ticketIds': [6], 'email': 'pending@x.com'},
        )

    resp = api_client.get(
        f'/plugin/x402/admin/orders/?organizer={event.organizer.slug}&event={event.slug}',
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body['pending']) == 1
    row = body['pending'][0]
    for k in ('paymentReference', 'createdAt', 'expiresAt', 'intendedPayer',
              'totalUsd', 'metadata', 'expectedChainId'):
        assert k in row, f'missing key: {k}'
    assert isinstance(row['createdAt'], int) and row['createdAt'] > 0
    assert isinstance(row['expiresAt'], int) and row['expiresAt'] > 0
    assert row['expectedChainId'] == 10
    assert row['metadata']['ticketIds'] == [6]
    assert row['metadata']['addonIds'] == [17, 18]
    assert row['metadata']['voucher'] == 'VOUCHER123'


@pytest.mark.django_db
def test_admin_orders_includes_legacy_wc_but_not_signed_message(
    api_client, event, get_order_and_payment,
):
    """WalletConnect direct-send rows merge into `completed`; daimo-era
    SignedMessage rows are intentionally excluded (pre-all-current-flows,
    not useful operational data)."""
    from pretix_eth.models import SignedMessage, WCPaymentAttempt
    from django.utils import timezone
    order, payment = get_order_and_payment()
    with scopes_disabled():
        SignedMessage.objects.create(
            signature='0x' + 'a' * 130,
            raw_message='msg', sender_address='0x' + '1' * 40,
            recipient_address='0x' + '2' * 40, chain_id=8453,
            order_payment=payment, transaction_hash='0x' + 'd' * 64,
            is_confirmed=True, invalid=False,
            created_at=timezone.now(),
        )
        WCPaymentAttempt.objects.create(
            tx_hash='0x' + 'e' * 64, quote_id='qid_1', order_code=order.code,
            payer='0x' + '3' * 40, chain_id=10,
            state=WCPaymentAttempt.STATE_COMPLETED,
        )

    resp = api_client.get(
        f'/plugin/x402/admin/orders/?organizer={event.organizer.slug}&event={event.slug}',
    )
    assert resp.status_code == 200
    body = resp.json()
    sources = sorted(r['source'] for r in body['completed'])
    assert sources == ['wc_attempt']  # SignedMessage intentionally excluded
    assert body['stats']['legacyCount'] == 1
    assert body['stats']['x402Count'] == 0
    assert body['stats']['completed'] == 1


@pytest.mark.django_db
def test_admin_stats_counts(api_client, event):
    with scopes_disabled():
        X402PendingOrder.objects.create(
            event=event, payment_reference='x402_p1', order_data={},
            total_usd=Decimal('5'),
            expires_at=__import__('django').utils.timezone.now() + __import__('datetime').timedelta(hours=1),
            intended_payer='0x' + '1' * 40,
        )
        X402CompletedOrder.objects.create(
            event=event, tx_hash='0x' + 'c' * 64, payment_reference='x402_s1',
            pretix_order_code='S1', payer='0x' + '1' * 40, chain_id=8453,
            total_usd=Decimal('10'), token_symbol='USDC',
        )

    resp = api_client.get(
        f'/plugin/x402/admin/stats/?organizer={event.organizer.slug}&event={event.slug}',
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['pending_count'] == 1
    assert body['completed_count'] == 1
    assert body['total_usd'] == '10.00'
