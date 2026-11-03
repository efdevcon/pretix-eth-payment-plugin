"""The UPI rail is an allow-list: offered only when every charged main
product in the cart (or in the order being re-paid) carries a rupee price in
the `upi_price_inr` item meta property. Add-ons follow their parent. The
rupee prices set the order's rate, so vouchers, fees and unpriced add-ons
convert at it.
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

from pretix_eth.payment_upi import UPI_PRICE_META, StripeCheckoutUPI, inr_amount, inr_rate


def _request(event, order_code=None):
    request = RequestFactory().get('/checkout/payment/')
    request.event = event
    request.organizer = event.organizer
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    if order_code:
        request.resolver_match = SimpleNamespace(kwargs={'order': order_code})
    return request


def _meta(event, item, name, value):
    prop, _ = ItemMetaProperty.objects.get_or_create(event=event, name=name, defaults={'default': ''})
    ItemMetaValue.objects.create(item=item, property=prop, value=value)


def _item(event, name, inr=None, usd='100.00', card=None):
    with scopes_disabled():
        item = Item.objects.create(event=event, name=name, default_price=Decimal(usd))
        if inr is not None:
            _meta(event, item, UPI_PRICE_META, inr)
        if card is not None:
            _meta(event, item, 'fiat_price_usd', card)
    return item


def _add_to_cart(request, event, item, addon_to=None, price=None):
    cart_id = get_or_create_cart_id(request)
    with scopes_disabled():
        return CartPosition.objects.create(
            event=event, item=item, price=item.default_price if price is None else Decimal(price), cart_id=cart_id,
            expires=timezone.now() + timezone.timedelta(hours=1), addon_to=addon_to,
        )


def _allowed(event, request):
    with scope(organizer=event.organizer):
        return StripeCheckoutUPI(event).is_allowed(request, total=Decimal('100.00'))


def _cart(request):
    with scopes_disabled():
        return list(CartPosition.objects.filter(cart_id=get_or_create_cart_id(request)).select_related('item', 'variation'))


@pytest.fixture
def upi_event(event):
    event.settings.set('payment_stripe_secret_key', 'sk_test_x')
    return event


@pytest.mark.django_db
def test_priced_product_in_cart_offers_upi(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', inr='2250'))
    assert _allowed(upi_event, request) is True


@pytest.mark.django_db
def test_unpriced_product_in_cart_hides_upi(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'GA'))
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_mixed_cart_hides_upi(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', inr='2250'))
    _add_to_cart(request, upi_event, _item(upi_event, 'GA'))
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_addons_follow_their_parent(upi_event):
    request = _request(upi_event)
    parent = _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', inr='2250'))
    _add_to_cart(request, upi_event, _item(upi_event, 'Shirt', usd='20.00'), addon_to=parent)
    assert _allowed(upi_event, request) is True

    request = _request(upi_event)
    parent = _add_to_cart(request, upi_event, _item(upi_event, 'GA'))
    _add_to_cart(request, upi_event, _item(upi_event, 'Priced add-on', inr='500', usd='20.00'), addon_to=parent)
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_empty_cart_hides_upi(upi_event):
    assert _allowed(upi_event, _request(upi_event)) is False


@pytest.mark.django_db
def test_rate_comes_from_list_prices_so_vouchers_scale(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', inr='2250'), price='50.00')  # 50% voucher
    rate = inr_rate(_cart(request))
    assert rate == Decimal('22.5')
    assert inr_amount(Decimal('50.00'), rate) == Decimal('1125.00')


@pytest.mark.django_db
def test_rate_pairs_the_rupee_price_with_the_card_price(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'GA', inr='3000', usd='100.00', card='150.00'))
    assert inr_rate(_cart(request)) == Decimal('20')


@pytest.mark.django_db
def test_unpriced_addons_convert_at_the_parent_rate(upi_event):
    request = _request(upi_event)
    parent = _add_to_cart(request, upi_event, _item(upi_event, 'India Resident', inr='2250'))
    _add_to_cart(request, upi_event, _item(upi_event, 'Shirt', usd='20.00'), addon_to=parent)
    rate = inr_rate(_cart(request))
    assert rate == Decimal('22.5')
    assert inr_amount(Decimal('120.00'), rate) == Decimal('2700.00')


@pytest.mark.django_db
def test_free_positions_carry_no_rate(upi_event):
    request = _request(upi_event)
    _add_to_cart(request, upi_event, _item(upi_event, 'Free pass', usd='0.00'))
    assert inr_rate(_cart(request)) is None
    assert _allowed(upi_event, request) is False


@pytest.mark.django_db
def test_quote_follows_the_payment_amount(upi_event, get_order_and_payment):
    """A crypto-created order re-paid by UPI carries a payment fee: the
    rupees follow the amount the payment collects, at the products' rate."""
    order, payment = get_order_and_payment(payment_kwargs={'provider': StripeCheckoutUPI.identifier})
    with scopes_disabled():
        OrderPosition.objects.create(order=order, item=_item(upi_event, 'GA', inr='2250'), price=Decimal('100.00'), positionid=1)
        payment.amount = Decimal('150.00')
        payment.save(update_fields=['amount'])
    with scope(organizer=upi_event.organizer):
        assert StripeCheckoutUPI(upi_event).quote(payment) == (Decimal('22.5'), Decimal('3375.00'))


@pytest.mark.django_db
def test_repay_follows_the_order_products(upi_event, get_order_and_payment):
    priced, plain = _item(upi_event, 'India Resident', inr='2250'), _item(upi_event, 'GA')
    for item, expected in ((priced, True), (plain, False)):
        order, _ = get_order_and_payment(payment_kwargs={'provider': StripeCheckoutUPI.identifier})
        with scopes_disabled():
            OrderPosition.objects.create(order=order, item=item, price=item.default_price, positionid=1)
        with scope(organizer=upi_event.organizer):
            assert StripeCheckoutUPI(upi_event).order_change_allowed(order) is expected
            # The payment-method chooser of the re-pay page asks is_allowed with the order code in the URL.
            assert StripeCheckoutUPI(upi_event).is_allowed(_request(upi_event, order.code), total=order.total) is expected
