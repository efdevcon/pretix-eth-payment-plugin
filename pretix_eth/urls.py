"""URL routes for the Pretix eth payment plugin.

- /plugin/wc/* — legacy WalletConnect direct-send flow (existing)
- /plugin/x402/* — new x402 flow (gasless USDC/USDT0 + direct ETH)

WC URLs are registered as `event_patterns` so they're reachable both on the
main domain at `/{organizer}/{event}/plugin/wc/...` AND on a custom event
domain at `/plugin/wc/...`. Without `event_patterns`, Pretix's custom-domain
URLconf (`event_domain_urlconf.py`) wouldn't load them — see
pretix/multidomain/event_domain_urlconf.py for the loading logic.

x402 URLs stay on `urlpatterns` (main-domain only, accessed cross-origin from
the storefront) because they aren't gated by a single event's checkout — the
storefront talks to them directly via the Pretix base URL.
"""
from django.urls import path
from pretix_eth import views, views_x402, views_admin

# Event-scoped plugin URLs. Pretix wraps each view with `_event_view` which
# auto-resolves `request.event` from the URL path (main domain) or domain
# mapping (custom domain), and passes `organizer` + `event` slugs as kwargs
# — view signatures must accept `**kwargs`.
event_patterns = [
    path('plugin/wc/payment-options/', views.payment_options, name='wc_payment_options'),
    path('plugin/wc/wallet-balances/', views.wallet_balances, name='wc_wallet_balances'),
    path('plugin/wc/challenge/',       views.challenge,        name='wc_challenge'),
    path('plugin/wc/create-quote/',    views.create_quote,     name='wc_create_quote'),
    path('plugin/wc/verify/',          views.verify,           name='wc_verify'),
]

urlpatterns = [
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
]
