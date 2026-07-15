# tests/core/test_urls_admin_require_live.py
"""The operator/admin routes must stay reachable when the Pretix event is
NOT live ("shop offline").

Pretix wraps every event-scoped plugin URL with `_event_view(...,
require_live=getattr(entry.pattern, '_require_live', True))`. When the event
is offline and `require_live` is True, `_event_view` short-circuits with the
`pretixpresale/event/offline.html` 403 page BEFORE the view runs — so the
token-gated admin endpoints (order dashboard, refunds, manual verify) return
that HTML instead of JSON, and the /tickets/admin dashboard shows nothing.

The admin endpoints enforce their own auth (`@require_pretix_admin_token` +
`_check_event_access_or_403`), so they must opt out of the presale live-gate
by carrying `_require_live = False` on their event-scoped URL patterns.

Buyer-facing routes intentionally keep the default (live-gated): there's
nothing to buy while the shop is offline.
"""
from pretix_eth.urls import event_patterns

ADMIN_ROUTE_NAMES = {
    'admin_orders', 'admin_stats', 'admin_refund',
    'admin_verify', 'admin_wc_refund', 'admin_wc_verify',
}


def _by_name(patterns):
    return {p.name: p for p in patterns if getattr(p, 'name', None)}


def test_admin_routes_opt_out_of_live_gate():
    by_name = _by_name(event_patterns)
    missing = ADMIN_ROUTE_NAMES - set(by_name)
    assert not missing, f'admin routes not registered in event_patterns: {missing}'

    for name in ADMIN_ROUTE_NAMES:
        pattern = by_name[name].pattern
        require_live = getattr(pattern, '_require_live', True)
        assert require_live is False, (
            f'{name} must set _require_live=False so it stays reachable when the '
            f'event is offline (got {require_live!r}); otherwise Pretix returns the '
            f'offline.html 403 before the token-gated view runs'
        )


def test_buyer_routes_keep_live_gate_default():
    """A buyer route (create-quote) should NOT be silently opted out — nothing
    to buy while the shop is offline, and this guards against a blanket
    require_live=False sweep."""
    by_name = _by_name(event_patterns)
    quote = by_name.get('wc_create_quote')
    assert quote is not None
    assert getattr(quote.pattern, '_require_live', True) is True
