# tests/core/test_views_item_pricing.py
"""Caching contract for the buyer-side item-pricing endpoint.

The dual-price chips (`$X crypto / $Y card`) are drawn client-side from
this endpoint's JSON. Its `fiat_after_voucher` field is CART-DEPENDENT
(computed from the buyer's CartPositions), but the URL never changes as
the buyer moves catalog -> redeem -> checkout. If the response is ever
stored in a shared/durable cache, a copy captured while the cart was
empty (fiat_after_voucher=null) is replayed on later cart pages, showing
the full undiscounted card price until a manual reload revalidates it.

So the endpoint must never be publicly/durably cacheable.
"""
import pytest
from decimal import Decimal
from django_scopes import scopes_disabled


def _get_pricing(client, event):
    return client.get(
        f'/plugin/wc/item-pricing/?organizer={event.organizer.slug}&event={event.slug}'
    )


@pytest.mark.django_db
def test_item_pricing_is_never_publicly_cached(client, event):
    """A voucher discount is cart-dependent but the URL is stable, so a
    `public` cache entry poisons later cart pages. The response must be
    marked no-store / private so browsers and CDNs re-fetch every page."""
    from pretix.base.models import Item, ItemCategory
    with scopes_disabled():
        cat = ItemCategory.objects.create(event=event, name='Admission', position=0)
        Item.objects.create(
            event=event, name='GA', admission=True,
            default_price=Decimal('999.00'), category=cat,
        )

    resp = _get_pricing(client, event)
    assert resp.status_code == 200, resp.content

    cache_control = (resp.headers.get('Cache-Control') or '').lower()
    # Must NOT be shared-cacheable: no `public`, and either `no-store` or
    # `private` + `no-cache`/`must-revalidate` so cart pages always revalidate.
    assert 'public' not in cache_control, (
        f'item-pricing must not be publicly cached (got {cache_control!r}); '
        'a stale empty-cart copy would be replayed on checkout pages'
    )
    assert 'no-store' in cache_control, (
        f'item-pricing must be no-store to stay cart-accurate (got {cache_control!r})'
    )


@pytest.mark.django_db
def test_item_pricing_returns_voucher_discounted_card_price_from_cart(client, event):
    """Source 2 (cart page, no ?voucher= in the URL): the endpoint reads the
    buyer's CartPosition, sees the applied voucher, and returns the DISCOUNTED
    card price in `fiat_after_voucher` — the exact value the buyer's chip showed
    wrong ($999 instead of the voucher price) before the caching fix.

    Item: crypto list price 1.00, card list price (fiat_price_usd) 999. A 15%
    voucher on the cart position -> crypto 0.85, so the card price scales the
    same 15% -> 999 * 0.85 = 849.15."""
    from datetime import timedelta
    from django.utils import timezone
    from pretix.base.models import (
        Item, ItemCategory, ItemMetaProperty, ItemMetaValue, Voucher, CartPosition,
    )
    with scopes_disabled():
        cat = ItemCategory.objects.create(event=event, name='Admission', position=0)
        item = Item.objects.create(
            event=event, name='GA', admission=True,
            default_price=Decimal('1.00'), category=cat,
        )
        prop = ItemMetaProperty.objects.create(event=event, name='fiat_price_usd')
        ItemMetaValue.objects.create(item=item, property=prop, value='999')
        voucher = Voucher.objects.create(
            event=event, code='PCT15', price_mode='percent', value=Decimal('15.00'),
        )
        cart_id = 'testcart@item-pricing'
        CartPosition.objects.create(
            event=event, cart_id=cart_id, item=item,
            price=Decimal('0.85'),
            listed_price=Decimal('1.00'),
            price_after_voucher=Decimal('0.85'),
            voucher=voucher,
            datetime=timezone.now(),
            expires=timezone.now() + timedelta(minutes=30),
        )

    # Bind the cart to the session the way Pretix does: the endpoint (called on
    # the root URL, so request.event isn't set) falls back to this session key.
    session = client.session
    session['current_cart_event_{}'.format(event.pk)] = cart_id
    session.save()

    # No ?voucher= param -> forces the cart-position path (Source 2).
    resp = _get_pricing(client, event)
    assert resp.status_code == 200, resp.content

    row = next(i for i in resp.json()['items'] if i['id'] == item.id)
    assert row['fiat_price_usd'] == '999'           # list card price, undiscounted
    assert row['fiat_after_voucher'] == '849.15'    # discounted the same 15% as crypto
