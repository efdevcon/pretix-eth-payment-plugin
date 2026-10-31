"""Regression tests for the WebKit cookie patch (`_install_webkit_cookie_fix`).

The bug: Pretix sends its CSRF and session cookies as
`SameSite=None; Secure; Partitioned` to every browser except iOS 12 /
macOS 10.14 Safari. Current WebKit (all iOS browsers, Safari on macOS) drops
Partitioned cookies in some flows (WebKit bug 306194), so the
`__Host-pretix_csrftoken` cookie is missing on submit and `/cart/add`
answers "CSRF verification failed" (403) for ~30-50% of iPhone buyers.

The patch makes WebKit get plain first-party cookies (no SameSite=None, no
Partitioned); every other browser keeps Pretix's behaviour.
"""
import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from pretix.helpers import cookies

from pretix_eth.apps import _install_webkit_cookie_fix

# Real user agents from the production 403s (2026-10-31), plus unaffected browsers.
IOS_SAFARI = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/26.6.1 Mobile/15E148 Safari/604.1'
)
IOS_CHROME = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 26_6_1 like Mac OS X) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) CriOS/156.0.8078.54 Mobile/15E148 Safari/604.1'
)
MAC_SAFARI = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/26.6.1 Safari/605.1.15'
)
DESKTOP_CHROME = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
)
ANDROID_CHROME = (
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36'
)


@pytest.fixture(autouse=True)
def _patched():
    orig = cookies.should_send_same_site_none
    _install_webkit_cookie_fix()
    yield
    cookies.should_send_same_site_none = orig


def _csrf_cookie(useragent):
    request = RequestFactory().get('/', HTTP_USER_AGENT=useragent, secure=True)
    response = HttpResponse()
    cookies.set_cookie_without_samesite(
        request, response, '__Host-pretix_csrftoken', 'token', max_age=60, path='/', secure=True,
    )
    return response.cookies['__Host-pretix_csrftoken']


@pytest.mark.parametrize('ua', [IOS_SAFARI, IOS_CHROME, MAC_SAFARI])
def test_webkit_gets_plain_first_party_cookie(ua):
    morsel = _csrf_cookie(ua)
    assert not morsel['samesite']
    assert not morsel.get('partitioned')
    # __Host- cookies are rejected without Secure: it must survive the patch.
    assert morsel['secure']


@pytest.mark.parametrize('ua', [DESKTOP_CHROME, ANDROID_CHROME])
def test_other_browsers_keep_pretix_behaviour(ua):
    morsel = _csrf_cookie(ua)
    assert morsel['samesite'] == 'None'
    assert morsel.get('partitioned')
    assert morsel['secure']


def test_install_is_idempotent():
    _install_webkit_cookie_fix()
    assert cookies.should_send_same_site_none(IOS_SAFARI) is False
    assert cookies.should_send_same_site_none(DESKTOP_CHROME)
