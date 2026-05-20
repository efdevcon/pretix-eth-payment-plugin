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
from pretix_eth import views, views_x402, views_admin


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
    ]


def _x402_routes():
    return [
        # Public per-event toggle state (read-only). Storefront polls this to
        # decide whether to call the gated endpoints — must remain reachable
        # even when the gates are flipped OFF, so it sits at the top.
        path('plugin/x402/settings/',              views_x402.settings,              name='x402_settings'),

        # x402 purchase flow
        path('plugin/x402/purchase/',              views_x402.purchase,              name='x402_purchase'),
        path('plugin/x402/payment-options/',       views_x402.payment_options,       name='x402_payment_options'),
        path('plugin/x402/relayer/prepare-authorization/',
             views_x402.prepare_authorization, name='x402_prepare_authorization'),
        path('plugin/x402/relayer/execute-transfer/',
             views_x402.execute_transfer, name='x402_execute_transfer'),
        path('plugin/x402/verify/',                views_x402.verify,                name='x402_verify'),

        # x402 admin
        path('plugin/x402/admin/orders/',  views_admin.admin_orders,  name='x402_admin_orders'),
        path('plugin/x402/admin/stats/',   views_admin.admin_stats,   name='x402_admin_stats'),
        path('plugin/x402/admin/refund/',  views_admin.admin_refund,  name='x402_admin_refund'),
        path('plugin/x402/admin/wc-refund/', views_admin.admin_wc_refund, name='x402_admin_wc_refund'),
        path('plugin/x402/admin/verify/',  views_admin.admin_verify,  name='x402_admin_verify'),
        path('plugin/x402/admin/wc-verify/', views_admin.admin_wc_verify, name='x402_admin_wc_verify'),
    ]


event_patterns = _wc_routes() + _x402_routes()
urlpatterns = _wc_routes() + _x402_routes()
