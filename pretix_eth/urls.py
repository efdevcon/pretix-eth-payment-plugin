"""URL routes for the Pretix eth payment plugin.

- /plugin/wc/* — legacy WalletConnect direct-send flow
- /plugin/x402/* — x402 flow (gasless USDC/USDT0 + direct ETH)

All plugin URLs are registered twice: once at root (`urlpatterns`) and once
event-scoped (`event_patterns`). The event-scoped registration is what makes
them reachable on a custom event domain (e.g. tickets.devcon.org/plugin/...)
— Pretix's `event_domain_urlconf.py` only loads `event_patterns` from plugins.
The root-level registration keeps legacy test paths and the buyer-auth
query-param flow intact, and is the path the wc_inject bundle uses on
main-domain deployments.

Django's `reverse()` disambiguates the two registrations by which kwargs match:
  reverse('plugins:pretix_eth:wc_payment_options')                   → /plugin/wc/payment-options/
  reverse(..., kwargs={'organizer':'X','event':'Y'})                 → /X/Y/plugin/wc/payment-options/
and `eventreverse(event, ...)` always provides the kwargs, so the wc_inject
bundle's `urlPrefix` always resolves to the event-scoped form on main domain
(and to the bare root form on a custom domain via `event_domain_urlconf`).
"""
from django.urls import path
from pretix_eth import views, views_x402, views_admin  # noqa: F401 (views_x402 kept for the commented-out x402 routes below)


# x402 is DISABLED: every `/plugin/x402/*` payment/admin route below is
# commented out, so those paths 404 at the routing layer and no x402 view
# code runs. The code (views_x402, the x402 admin views) stays in the tree —
# re-enable by uncommenting the routes in `_x402_routes()`.
#
# The WalletConnect admin tools (`wc-refund`, `wc-verify`) historically sat
# under the `/plugin/x402/admin/` path prefix but serve the ACTIVE
# WalletConnect flow, so they now live in `_wc_routes()` and stay registered
# (their URL strings and route names are unchanged).


# Routes — registered twice with fresh URLPattern instances per registration.
# Pretix's `plugin_event_urls` mutates `entry.callback` on event_patterns to
# wrap each view with `_event_view`; if we shared `URLPattern` objects across
# both lists the root-level handler would also become event-wrapped (and
# would 500 when no event URL kwargs are present). The factory functions
# build fresh instances per registration.

def _wc_routes():
    return [
        path('plugin/wc/payment-options/', views.payment_options, name='wc_payment_options'),
        path('plugin/wc/wallet-balances/', views.wallet_balances, name='wc_wallet_balances'),
        path('plugin/wc/challenge/',       views.challenge,        name='wc_challenge'),
        path('plugin/wc/create-quote/',    views.create_quote,     name='wc_create_quote'),
        path('plugin/wc/verify/',          views.verify,           name='wc_verify'),
        path('plugin/wc/client-info/',     views.client_info,      name='wc_client_info'),
        path('plugin/wc/admin/fiat-blocked-items.js',
             views.admin_fiat_blocked_items_js, name='wc_admin_fiat_blocked_items_js'),
        path('plugin/wc/order-redirect.js',
             views.order_redirect_js, name='wc_order_redirect_js'),
        path('plugin/wc/item-pricing/',
             views.item_pricing, name='wc_item_pricing'),
        path('plugin/wc/item-pricing.js',
             views.item_pricing_js, name='wc_item_pricing_js'),
        # WalletConnect admin tools. Kept under the legacy `/plugin/x402/admin/`
        # path + route names for backward compatibility with existing admin
        # callers, but grouped here because they serve the WC flow and must
        # survive the x402 kill-switch (see X402_ENABLED above).
        path('plugin/x402/admin/wc-refund/', views_admin.admin_wc_refund, name='x402_admin_wc_refund'),
        path('plugin/x402/admin/wc-verify/', views_admin.admin_wc_verify, name='x402_admin_wc_verify'),
    ]


def _x402_routes():
    # x402 DISABLED — all routes commented out (see module note above).
    # wc-refund / wc-verify are NOT here: they serve the WalletConnect flow
    # and stay registered in `_wc_routes()`. Uncomment to re-enable x402.
    return [
        # Public per-event toggle state (read-only). Storefront polls this to
        # decide whether to call the gated endpoints — must remain reachable
        # even when the gates are flipped OFF, so it sits at the top.
        # path('plugin/x402/settings/',              views_x402.settings,              name='x402_settings'),

        # x402 purchase flow
        # path('plugin/x402/purchase/',              views_x402.purchase,              name='x402_purchase'),
        # path('plugin/x402/payment-options/',       views_x402.payment_options,       name='x402_payment_options'),
        # path('plugin/x402/relayer/prepare-authorization/',
        #      views_x402.prepare_authorization, name='x402_prepare_authorization'),
        # path('plugin/x402/relayer/execute-transfer/',
        #      views_x402.execute_transfer, name='x402_execute_transfer'),
        # path('plugin/x402/verify/',                views_x402.verify,                name='x402_verify'),

        # x402 admin (wc-refund / wc-verify live in _wc_routes — they serve
        # the WalletConnect flow and stay registered)
        # path('plugin/x402/admin/orders/',  views_admin.admin_orders,  name='x402_admin_orders'),
        # path('plugin/x402/admin/stats/',   views_admin.admin_stats,   name='x402_admin_stats'),
        # path('plugin/x402/admin/refund/',  views_admin.admin_refund,  name='x402_admin_refund'),
        # path('plugin/x402/admin/verify/',  views_admin.admin_verify,  name='x402_admin_verify'),
    ]


event_patterns = _wc_routes() + _x402_routes()
urlpatterns = _wc_routes() + _x402_routes()
