"""URL routes for the Pretix eth payment plugin.

- /plugin/wc/*    — WalletConnect direct-send buyer flow (active)
- /plugin/admin/* — operator/admin tools (order dashboard, refunds, manual
                    verify) for BOTH the WalletConnect and x402 flows
                    (order/stats aggregate both). Always registered.
- /plugin/x402/*  — x402 gasless buyer flow (currently DISABLED — see below)

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

## x402 status

The x402 gasless BUYER flow (purchase / payment-options / relayer / verify /
settings) is DISABLED: those routes are commented out in `_x402_routes()`, so
the paths 404 and no x402 buyer-payment view runs. The code stays in the tree
— re-enable by uncommenting.

The admin tools in `_admin_routes()` are NOT part of that gate. They are
token- + permission-gated operator endpoints, and the order/stats views
aggregate WalletConnect payments too, so the /tickets/admin dashboard depends
on them regardless of x402. They live under `/plugin/admin/*` (renamed from
the legacy `/plugin/x402/admin/*` misnomer — these are shared crypto-admin
tools, not x402-only; the devcon-next proxies were updated to match).
"""
from django.urls import path
from pretix.multidomain import event_path
from pretix_eth import views, views_x402, views_admin  # noqa: F401 (views_x402 kept for the commented-out x402 routes below)


# Routes — registered twice with fresh URLPattern instances per registration.
# Pretix's `plugin_event_urls` mutates `entry.callback` on event_patterns to
# wrap each view with `_event_view`; if we shared `URLPattern` objects across
# both lists the root-level handler would also become event-wrapped (and
# would 500 when no event URL kwargs are present). The factory functions
# build fresh instances per registration.

def _wc_routes():
    """WalletConnect direct-send buyer flow + injected buyer-facing bundles."""
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
    ]


def _admin_routes():
    """Operator/admin tools — always registered, independent of the x402
    buyer-flow gate below. All are token- + permission-gated (`can_view_orders`
    / `can_change_orders`) and organizer-scoped. `admin_orders` / `admin_stats`
    aggregate BOTH WalletConnect and x402 payments, so the /tickets/admin
    dashboard needs them for the active WC flow.

    Paths live under `/plugin/admin/*` (renamed from the legacy
    `/plugin/x402/admin/*` misnomer — these are shared crypto-admin tools, not
    x402-only). The devcon-next admin proxies were updated to match.

    `require_live=False`: registered via Pretix's `event_path` so these routes
    stay reachable when the event is NOT live ("shop offline"). Pretix wraps
    event-scoped plugin URLs with `_event_view(require_live=...)`, and the
    default (True) makes an offline event return the `offline.html` 403 page
    BEFORE the view runs — which blanked the /tickets/admin dashboard exactly
    when operators need it (recovery, refunds, manual verify). These endpoints
    do their own auth (`@require_pretix_admin_token` + `_check_event_access_or_403`),
    so opting out of the presale live-gate changes nothing about who may call
    them — it just lets the token-gated view run regardless of shop status.
    """
    return [
        event_path('plugin/admin/orders/',    views_admin.admin_orders,    name='admin_orders',    require_live=False),
        event_path('plugin/admin/stats/',     views_admin.admin_stats,     name='admin_stats',     require_live=False),
        event_path('plugin/admin/refund/',    views_admin.admin_refund,    name='admin_refund',    require_live=False),
        event_path('plugin/admin/verify/',    views_admin.admin_verify,    name='admin_verify',    require_live=False),
        event_path('plugin/admin/wc-refund/', views_admin.admin_wc_refund, name='admin_wc_refund', require_live=False),
        event_path('plugin/admin/wc-verify/', views_admin.admin_wc_verify, name='admin_wc_verify', require_live=False),
    ]


def _x402_routes():
    # x402 gasless BUYER flow — DISABLED (all routes commented out; see module
    # docstring). Admin tools live in `_admin_routes()` and stay registered.
    # Uncomment to re-enable the buyer flow.
    return [
        # Public per-event toggle state (read-only). Storefront polls this to
        # decide whether to call the gated endpoints.
        # path('plugin/x402/settings/',              views_x402.settings,              name='x402_settings'),

        # x402 purchase flow
        # path('plugin/x402/purchase/',              views_x402.purchase,              name='x402_purchase'),
        # path('plugin/x402/payment-options/',       views_x402.payment_options,       name='x402_payment_options'),
        # path('plugin/x402/relayer/prepare-authorization/',
        #      views_x402.prepare_authorization, name='x402_prepare_authorization'),
        # path('plugin/x402/relayer/execute-transfer/',
        #      views_x402.execute_transfer, name='x402_execute_transfer'),
        # path('plugin/x402/verify/',                views_x402.verify,                name='x402_verify'),
    ]


event_patterns = _wc_routes() + _admin_routes() + _x402_routes()
urlpatterns = _wc_routes() + _admin_routes() + _x402_routes()
