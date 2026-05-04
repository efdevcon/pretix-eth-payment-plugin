# tests/core/test_x402_pretix_client.py
import pytest
from django_scopes import scopes_disabled
from pretix_eth.x402.pretix_client import create_pretix_order, confirm_x402_payment


@pytest.mark.django_db
def test_create_pretix_order_makes_pretix_order(event):
    """Creates a real Pretix Order via the ORM (internal API -- no HTTP)."""
    from pretix.base.models import Item, ItemCategory
    from decimal import Decimal
    with scopes_disabled():
        cat = ItemCategory.objects.create(event=event, name='Admission', position=0)
        item = Item.objects.create(
            event=event, name='GA', admission=True,
            default_price=Decimal('10.00'), category=cat,
        )
        order_data = {
            'email': 'test@example.com',
            'tickets': [{'itemId': item.id, 'quantity': 1}],
            'answers': [],
            'attendee': {'name': {'given_name': 'T', 'family_name': 'U'}},
        }
        order = create_pretix_order(event=event, order_data=order_data, total_usd='10.00')
        assert order is not None
        assert order.positions.count() == 1


@pytest.mark.django_db
def test_confirm_x402_payment_marks_confirmed(event):
    """confirm_x402_payment sets info_data and transitions payment state."""
    from pretix.base.models import Item, ItemCategory
    from decimal import Decimal
    with scopes_disabled():
        cat = ItemCategory.objects.create(event=event, name='Admission', position=0)
        item = Item.objects.create(
            event=event, name='GA', admission=True,
            default_price=Decimal('10.00'), category=cat,
        )
        order_data = {
            'email': 'test@example.com',
            'tickets': [{'itemId': item.id, 'quantity': 1}],
            'answers': [],
            'attendee': {},
        }
        order = create_pretix_order(event=event, order_data=order_data, total_usd='10.00')
        payment = confirm_x402_payment(
            order=order, tx_hash='0x' + 'f' * 64,
            payer='0x' + '1' * 40, chain_id=8453, token_symbol='USDC',
        )
        assert payment is not None
        assert payment.info_data['tx_hash'] == '0x' + 'f' * 64
        assert payment.state == 'confirmed'
