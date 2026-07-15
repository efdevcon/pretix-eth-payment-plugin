# tests/core/test_views_matomo_bridge.py
"""The Matomo cookie-domain bridge (`matomo-bridge.js`).

The Tracking-codes plugin boots Matomo on the shop but exposes no
`setCookieDomain` setting, so tickets.devcon.org computes a cookie name
hashed from its own host and never reads the `_pk_id` cookie devcon.org
sets for `.devcon.org` — the same browser gets a different visitor id per
domain and cross-domain funnels can't connect. The bridge pre-queues
`setCookieDomain`/`setDomains` (queue order beats the plugin's DOM-ready
`trackPageView`) so both domains share one first-party visitor cookie.
"""
import pytest
from django.test import override_settings

from pretix_eth.views import _matomo_cookie_domain


@pytest.mark.parametrize('host,expected', [
    ('tickets.devcon.org', '*.devcon.org'),      # prod shop
    ('devcon.org', '*.devcon.org'),              # apex
    ('dcdev2.ticketh.xyz', '*.ticketh.xyz'),     # dev shop
    ('tickets.devcon.org:8443', '*.devcon.org'),  # port stripped
    ('TICKETS.DEVCON.ORG', '*.devcon.org'),      # case-normalized
    ('localhost', None),                         # no parent domain to share
    ('testserver', None),
    ('127.0.0.1', None),                         # IP literal — no wildcard cookies
    ('127.0.0.1:8000', None),
    ('', None),
])
def test_matomo_cookie_domain_derivation(host, expected):
    assert _matomo_cookie_domain(host) == expected


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['tickets.devcon.org', 'testserver'])
def test_matomo_bridge_js_served_with_pushes():
    """On a real host the JS must queue setCookieDomain + setDomains —
    and nothing else that could reorder or duplicate the tracking
    plugin's own pushes (no trackPageView here!).

    Uses RequestFactory: pretix's multidomain middleware 400s unknown
    hosts on the test client, and the host→domain logic is entirely
    inside the view."""
    from django.test import RequestFactory
    from pretix_eth.views import matomo_bridge_js
    request = RequestFactory().get('/plugin/wc/matomo-bridge.js', HTTP_HOST='tickets.devcon.org')
    resp = matomo_bridge_js(request)
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('application/javascript')
    body = resp.content.decode()
    assert '"*.devcon.org"' in body
    assert 'setCookieDomain' in body
    assert 'setDomains' in body
    assert 'trackPageView' not in body


@pytest.mark.django_db
def test_matomo_bridge_js_noop_on_single_label_host(client):
    """localhost/testserver: no parent domain to share — serve a comment-only
    no-op instead of setting a nonsense cookie domain."""
    resp = client.get('/plugin/wc/matomo-bridge.js')  # host = testserver
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'setCookieDomain' not in body
