# tests/core/test_signals_order_redirect.py
"""Post-checkout redirect to the storefront order page.

`inject_order_redirect` puts a <script> on Pretix's order-detail page that
bounces the buyer to `frontend_order_url_template` (devcon.org/.../order/...).

Pretix flags a just-completed landing with one of three query params, and
which one you get depends on how the order finished:

  thanks=1    checkoutflow.ConfirmStep.get_order_url() — nothing left to pay.
              This is the FREE-ORDER path (100%-off voucher), which used to
              be missed: only `thanks=yes` was accepted, so buyers redeeming
              a free voucher were left sitting on Pretix's own order page.
  thanks=yes  views/order.OrderPayComplete, order not PAID yet.
  paid=yes    views/order.OrderPayComplete, order came back PAID.

A flag alone isn't enough — the order must also be PAID, because `thanks=1`
is equally what an unpaid bank-transfer order lands with, and that buyer
needs Pretix's payment instructions.
"""
import pytest
from django.test import RequestFactory

from pretix.base.models import Order

from pretix_eth.signals import inject_order_redirect

FRONTEND_TEMPLATE = 'https://devcon.org/en/tickets/store/order/{code}/{secret}/'


def _request(order, query):
    """A GET on the order-detail page, resolver_match faked the way the
    html_head signal sees it."""
    request = RequestFactory().get(f'/order/{order.code}/{order.secret}/{query}')
    request.resolver_match = type(
        'M', (), {'url_name': 'event.order', 'kwargs': {'order': order.code, 'secret': order.secret}}
    )()
    return request


@pytest.fixture
def paid_free_order(event, get_order_and_payment):
    """A 100%-voucher order: total 0, already PAID, no payment to execute."""
    order, _ = get_order_and_payment(
        order_kwargs={'total': 0, 'status': Order.STATUS_PAID},
        payment_kwargs={'amount': '0.00', 'provider': 'free'},
    )
    event.settings.set('payment_walletconnect_frontend_order_url_template', FRONTEND_TEMPLATE)
    return order


@pytest.mark.django_db
@pytest.mark.parametrize('query', ['?thanks=1', '?thanks=yes', '?paid=yes'])
def test_redirect_injected_on_every_completed_landing(event, paid_free_order, query):
    html = inject_order_redirect(event, _request(paid_free_order, query))
    assert 'order_redirect' in html or '<script' in html, f'no redirect for {query}'
    assert paid_free_order.code in html


@pytest.mark.django_db
def test_free_voucher_order_redirects(event, paid_free_order):
    """The regression this covers: a free order lands on `?thanks=1`."""
    assert '<script' in inject_order_redirect(event, _request(paid_free_order, '?thanks=1'))


@pytest.mark.django_db
def test_no_redirect_without_a_completion_flag(event, paid_free_order):
    """Revisiting the order later (email link, bookmark) must stay on Pretix."""
    assert inject_order_redirect(event, _request(paid_free_order, '')) == ''
    assert inject_order_redirect(event, _request(paid_free_order, '?thanks=no')) == ''


@pytest.mark.django_db
def test_no_redirect_for_unpaid_order_placed_without_payment(event, get_order_and_payment):
    """`thanks=1` also fires for an order placed with money still owed —
    that buyer needs Pretix's payment instructions, not the storefront."""
    order, _ = get_order_and_payment(order_kwargs={'status': Order.STATUS_PENDING})
    event.settings.set('payment_walletconnect_frontend_order_url_template', FRONTEND_TEMPLATE)
    assert inject_order_redirect(event, _request(order, '?thanks=1')) == ''


@pytest.mark.django_db
@pytest.mark.parametrize('query', ['?thanks=yes', '?paid=yes'])
def test_unpaid_order_still_redirects_after_a_payment_attempt(event, get_order_and_payment, query):
    """REGRESSION GUARD for the pre-existing card/crypto flow.

    `OrderPayComplete` emits `?thanks=yes` exactly when the order it holds is
    NOT paid (async capture, or a confirm that landed after the in-memory copy
    was read). Those buyers have always been redirected, so requiring PAID here
    would silently break the flow this receiver was written for."""
    order, _ = get_order_and_payment(order_kwargs={'status': Order.STATUS_PENDING})
    event.settings.set('payment_walletconnect_frontend_order_url_template', FRONTEND_TEMPLATE)
    assert '<script' in inject_order_redirect(event, _request(order, query))


@pytest.mark.django_db
def test_no_redirect_when_template_unset(event, get_order_and_payment):
    order, _ = get_order_and_payment(order_kwargs={'status': Order.STATUS_PAID})
    event.settings.delete('payment_walletconnect_frontend_order_url_template')
    assert inject_order_redirect(event, _request(order, '?thanks=1')) == ''


@pytest.mark.django_db
def test_no_redirect_on_sub_pages(event, paid_free_order):
    """/pay/, /cancel/, /change/ — the buyer still has work to do on Pretix."""
    request = _request(paid_free_order, '?thanks=1')
    request.resolver_match = type(
        'M', (), {'url_name': 'event.order.pay', 'kwargs': {'order': paid_free_order.code}}
    )()
    assert inject_order_redirect(event, request) == ''
