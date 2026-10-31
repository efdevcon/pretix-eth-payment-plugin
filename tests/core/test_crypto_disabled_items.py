"""Per-item `crypto_disabled` metadata: a cart (or an order being re-paid)
that holds such an item never offers the crypto rail, mirroring how
`fiat_disabled` hides every card rail. Both flags share one lookup helper, so
the fiat restrictor is covered here too as a regression guard.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone
from django_scopes import scope, scopes_disabled
from pretix.base.models import CartPosition, Item, ItemMetaProperty, ItemMetaValue, Order, OrderPosition
from pretix.base.payment import BasePaymentProvider
from pretix.presale.views.cart import get_or_create_cart_id

from pretix_eth.payment import WalletConnectPayment


class _FiatProvider(BasePaymentProvider):
    identifier = 'testfiat'
    verbose_name = 'Test card rail'


def _request(event, order_code=None):
    request = RequestFactory().get('/checkout/payment/')
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    if order_code:
        request.resolver_match = SimpleNamespace(kwargs={'order': order_code})
    return request


def _item(event, name, flag=None):
    with scopes_disabled():
        item = Item.objects.create(event=event, name=name, default_price=Decimal('100.00'))
        if flag:
            prop, _ = ItemMetaProperty.objects.get_or_create(event=event, name=flag, defaults={'default': ''})
            ItemMetaValue.objects.create(item=item, property=prop, value='true')
    return item


def _allowed(provider, request):
    # Pretix's middleware activates the organizer scope for every presale
    # request; the cart/order lookups behind is_allowed rely on it.
    with scope(organizer=provider.event.organizer):
        return provider.is_allowed(request)


def _add_to_cart(request, event, item, addon_to=None):
    cart_id = get_or_create_cart_id(request)
    with scopes_disabled():
        return CartPosition.objects.create(
            event=event, item=item, price=item.default_price, cart_id=cart_id,
            expires=timezone.now() + timezone.timedelta(hours=1), addon_to=addon_to,
        )


@pytest.fixture
def configured(event):
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')
    return event


@pytest.mark.django_db
def test_crypto_disabled_item_in_cart_hides_crypto(configured):
    request = _request(configured)
    _add_to_cart(request, configured, _item(configured, 'Card only', 'crypto_disabled'))
    assert _allowed(WalletConnectPayment(configured), request) is False


@pytest.mark.django_db
def test_plain_item_in_cart_keeps_crypto(configured):
    request = _request(configured)
    _add_to_cart(request, configured, _item(configured, 'GA'))
    assert _allowed(WalletConnectPayment(configured), request) is True


@pytest.mark.django_db
def test_crypto_disabled_addon_follows_its_parent(configured):
    request = _request(configured)
    parent = _add_to_cart(request, configured, _item(configured, 'GA'))
    _add_to_cart(request, configured, _item(configured, 'Shirt', 'crypto_disabled'), addon_to=parent)
    assert _allowed(WalletConnectPayment(configured), request) is True


@pytest.mark.django_db
def test_crypto_disabled_item_on_order_being_repaid_hides_crypto(configured):
    item = _item(configured, 'Card only', 'crypto_disabled')
    with scopes_disabled():
        sc = configured.organizer.sales_channels.get(identifier='web')
        order = Order.objects.create(
            event=configured, email='b@example.com', status=Order.STATUS_PENDING,
            total=Decimal('100.00'), code='REPAY1', datetime=timezone.now(),
            expires=timezone.now(), sales_channel=sc, locale='en',
        )
        OrderPosition.objects.create(order=order, item=item, price=item.default_price, positionid=1)
    request = _request(configured, order_code=order.code)
    assert _allowed(WalletConnectPayment(configured), request) is False


@pytest.mark.django_db
def test_fiat_disabled_item_still_hides_card_rails(configured):
    """Regression guard for the shared lookup: the fiat restrictor keeps
    blocking non-crypto providers for crypto-only items."""
    request = _request(configured)
    _add_to_cart(request, configured, _item(configured, 'Crypto only', 'fiat_disabled'))
    assert _allowed(_FiatProvider(configured), request) is False
    assert _allowed(WalletConnectPayment(configured), request) is True


@pytest.mark.django_db
def test_fiat_rail_untouched_by_crypto_disabled(configured):
    request = _request(configured)
    _add_to_cart(request, configured, _item(configured, 'Card only', 'crypto_disabled'))
    assert _allowed(_FiatProvider(configured), request) is True
