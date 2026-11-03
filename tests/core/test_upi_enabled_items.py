"""The UPI rail is an allow-list: offered only when every main product in the
cart (or in the order being re-paid) carries the `upi_enabled` item flag.
Add-ons follow their parent. The restriction can be switched off per event.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone
from django_scopes import scope, scopes_disabled
from pretix.base.models import CartPosition, Item, ItemMetaProperty, ItemMetaValue, OrderPosition
from pretix.presale.views.cart import get_or_create_cart_id

from pretix_eth.apps import UPI_ENABLED_FLAG
from pretix_eth.payment_upi import StripeCheckoutUPI


def _request(event, order_code=None):
    request = RequestFactory().get('/checkout/payment/')
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    if order_code:
        request.resolver_match = SimpleNamespace(kwargs={'order': order_code})
    return request


def _item(event, name, flagged):
    with scopes_disabled():
        item = Item.objects.create(event=event, name=name, default_price=Decimal('100.00'))
        if flagged:
            prop, _ = ItemMetaProperty.objects.get_or_create(event=event, name=UPI_ENABLED_FLAG, defaults={'default': ''})
            ItemMetaValue.objects.create(item=item, property=prop, value='1')
    return item


def _add_to_cart(request, event, item, addon_to=None):
    cart_id = get_or_create_cart_id(request)
    with scopes_disabled():
        return CartPosition.objects.create(
            event=event, item=item, price=item.default_price, cart_id=cart_id,
            expires=timezone.now() + timezone.timedelta(hours=1), addon_to=addon_to,
        )


def _allowed(event, request):
    with scope(organizer=event.organizer):
        return StripeCheckoutUPI(event).is_allowed(request, total=Decimal('100.00'))


@pytest.fixture
def upi_event(event):
    event.settings.set('payment_stripe_secret_key', 'sk_test_x')
    return event


@pytest.mark.django_db
def test_flagged_product_in_cart_offers_upi(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', flagged=True))
    assert _allowed(upi_event, request) is True


@pytest.mark.django_db
def test_unflagged_product_in_cart_hides_upi(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'GA', flagged=False))
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_mixed_cart_hides_upi(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', flagged=True))
    _add_to_cart(request, upi_event, _item(upi_event, 'GA', flagged=False))
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_addons_follow_their_parent(upi_event):
    request = _request(upi_event)
    parent = _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', flagged=True))
    _add_to_cart(request, upi_event, _item(upi_event, 'Shirt', flagged=False), addon_to=parent)
    assert _allowed(upi_event, request) is True

    request = _request(upi_event)
    parent = _add_to_cart(request, upi_event, _item(upi_event, 'GA', flagged=False))
    _add_to_cart(request, upi_event, _item(upi_event, 'Flagged add-on', flagged=True), addon_to=parent)
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_empty_cart_hides_upi(upi_event):
    assert _allowed(upi_event, _request(upi_event)) is False


@pytest.mark.django_db
def test_restriction_can_be_switched_off(upi_event):
    upi_event.settings.set('payment_stripe_checkout_upi_restrict_to_flagged_items', False)
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'GA', flagged=False))
    assert _allowed(upi_event, request) is True


@pytest.mark.django_db
def test_repay_follows_the_order_products(upi_event, get_order_and_payment):
    flagged, plain = _item(upi_event, 'India Resident', True), _item(upi_event, 'GA', False)
    for item, expected in ((flagged, True), (plain, False)):
        order, _ = get_order_and_payment(payment_kwargs={'provider': StripeCheckoutUPI.identifier})
        with scopes_disabled():
            OrderPosition.objects.create(order=order, item=item, price=item.default_price, positionid=1)
        with scope(organizer=upi_event.organizer):
            assert StripeCheckoutUPI(upi_event).order_change_allowed(order) is expected
            # The payment-method chooser of the re-pay page asks is_allowed with the order code in the URL.
            assert StripeCheckoutUPI(upi_event).is_allowed(_request(upi_event, order.code), total=order.total) is expected
