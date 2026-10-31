"""The Stripe chooser label carries the live card markup ("+$500 · Credit
Card") so a buyer comparing against the crypto price sees the premium. Once
the crypto rail is not on offer for this cart (provider window closed, or a
`crypto_disabled` item in the cart) the rows already show the card price, so
the prefix must go: "+$500" next to "$999" reads as a second surcharge.
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone
from django_scopes import scopes_disabled
from pretix.base.models import CartPosition, Item, ItemMetaProperty, ItemMetaValue
from pretix.base.reldate import RelativeDateWrapper
from pretix.plugins.stripe.payment import StripeMethod

from pretix_eth import apps as plugin_apps


def _stripe_card(event):
    cls = next(c for c in StripeMethod.__subclasses__() if c.identifier == 'stripe')
    return cls(event)


def _meta(event, item, name, value):
    with scopes_disabled():
        prop, _ = ItemMetaProperty.objects.get_or_create(event=event, name=name, defaults={'default': ''})
        ItemMetaValue.objects.create(item=item, property=prop, value=value)


@pytest.fixture
def ga_in_cart(event):
    """GA at $499 crypto / $999 card, one position in the captured cart."""
    event.settings.set('payment_walletconnect_receive_address', '0x' + '2' * 40)
    event.settings.set('payment_walletconnect_wc_project_id', 'p1')
    with scopes_disabled():
        item = Item.objects.create(event=event, name='GA', default_price=Decimal('499.00'))
        _meta(event, item, 'fiat_price_usd', '999')
        cp = CartPosition.objects.create(
            event=event, cart_id='chooser@test', item=item, price=Decimal('499.00'),
            datetime=timezone.now(), expires=timezone.now() + datetime.timedelta(minutes=30),
        )
    ctx = plugin_apps._fee_exempt_ctx
    ctx.positions = [cp]
    yield item
    ctx.positions = None


@pytest.mark.django_db
def test_label_carries_markup_in_dual_mode(event, ga_in_cart):
    with scopes_disabled():
        assert _stripe_card(event).public_name.startswith('+500')  # fixture event is EUR


@pytest.mark.django_db
def test_label_drops_markup_after_cutoff(event, ga_in_cart):
    event.settings.set(
        'payment_walletconnect__availability_date',
        RelativeDateWrapper(timezone.now() - datetime.timedelta(days=1)),
    )
    with scopes_disabled():
        assert not _stripe_card(event).public_name.startswith('+')


@pytest.mark.django_db
def test_label_drops_markup_when_cart_holds_crypto_disabled_item(event, ga_in_cart):
    _meta(event, ga_in_cart, 'crypto_disabled', 'true')
    with scopes_disabled():
        assert not _stripe_card(event).public_name.startswith('+')


@pytest.mark.django_db
def test_label_drops_markup_when_crypto_rail_disabled(event, ga_in_cart):
    event.settings.set('payment_walletconnect__enabled', False)
    with scopes_disabled():
        assert not _stripe_card(event).public_name.startswith('+')
