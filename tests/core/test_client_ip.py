"""Regression tests for `get_client_ip` header resolution.

The launch bug: behind the Cloudflare -> host chain the socket peer is
empty, so tokenless buyer calls resolved to the literal 'unknown' and all
buyers shared one rate-limit bucket. These tests lock in that direct buyer
calls resolve to the real client IP from CF/host headers.
"""
from pretix_eth.x402.auth import get_client_ip


class _Req:
    """Minimal request stub — get_client_ip only touches `.META`, `.path`,
    and the `_pretix_team` attribute (set by the auth decorators)."""
    def __init__(self, meta, team=None):
        self.META = meta
        self.path = '/plugin/wc/verify/'
        if team is not None:
            self._pretix_team = team


def test_tokenless_prefers_cf_connecting_ip():
    req = _Req({
        'REMOTE_ADDR': '',  # empty socket behind the proxy chain
        'HTTP_CF_CONNECTING_IP': '1.2.3.4',
        'HTTP_X_REAL_IP': '9.9.9.9',
        'HTTP_X_FORWARDED_FOR': '8.8.8.8',
    })
    assert get_client_ip(req) == '1.2.3.4'


def test_tokenless_falls_back_to_x_real_ip():
    # Mirrors the actual launch deployment: CF-Connecting-IP absent,
    # X-Real-IP carries the real client IP.
    req = _Req({
        'REMOTE_ADDR': '',
        'HTTP_X_REAL_IP': '83.79.83.17',
        'HTTP_X_FORWARDED_FOR': '83.79.83.17',
    })
    assert get_client_ip(req) == '83.79.83.17'


def test_tokenless_falls_back_to_xff_first():
    req = _Req({
        'REMOTE_ADDR': '',
        'HTTP_X_FORWARDED_FOR': '5.6.7.8, 10.0.0.1',
    })
    assert get_client_ip(req) == '5.6.7.8'


def test_tokenless_regression_never_unknown_when_real_ip_present():
    # The exact launch failure: real IP in X-Real-IP, empty socket. Must
    # NOT collapse to 'unknown' (which shared one bucket across all buyers).
    req = _Req({'REMOTE_ADDR': '', 'HTTP_X_REAL_IP': '203.0.113.7'})
    assert get_client_ip(req) != 'unknown'
    assert get_client_ip(req) == '203.0.113.7'


def test_tokenless_unknown_only_when_no_headers():
    req = _Req({'REMOTE_ADDR': ''})
    assert get_client_ip(req) == 'unknown'


def test_token_path_prefers_pretix_buyer_ip():
    # Token-authenticated proxy call: the injected buyer-IP header wins
    # over CF/host headers (which would be the proxy's own edge IP).
    req = _Req(
        {
            'REMOTE_ADDR': '10.0.0.5',
            'HTTP_X_PRETIX_BUYER_IP': '70.70.70.70',
            'HTTP_CF_CONNECTING_IP': '1.2.3.4',
            'HTTP_X_FORWARDED_FOR': '5.6.7.8',
        },
        team=object(),
    )
    assert get_client_ip(req) == '70.70.70.70'


def test_token_path_falls_back_to_xff():
    req = _Req(
        {'REMOTE_ADDR': '10.0.0.5', 'HTTP_X_FORWARDED_FOR': '5.6.7.8'},
        team=object(),
    )
    assert get_client_ip(req) == '5.6.7.8'
