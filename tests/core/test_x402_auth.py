# tests/core/test_x402_auth.py
import pytest
from django.http import HttpRequest, JsonResponse
from pretix_eth.x402.auth import require_pretix_token, noop_auth


def _request(headers=None):
    r = HttpRequest()
    r.META = {('HTTP_' + k.upper().replace('-', '_')): v for k, v in (headers or {}).items()}
    return r


def test_no_auth_header_returns_401():
    """No Authorization header → always rejected (no dev-mode bypass)."""
    @require_pretix_token
    def view(req):
        return JsonResponse({'ok': True})

    resp = view(_request())
    assert resp.status_code == 401


def test_wrong_format_returns_401():
    @require_pretix_token
    def view(req):
        return JsonResponse({'ok': True})

    resp = view(_request(headers={'Authorization': 'Bearer xyz'}))
    assert resp.status_code == 401


def test_empty_token_returns_401():
    @require_pretix_token
    def view(req):
        return JsonResponse({'ok': True})

    resp = view(_request(headers={'Authorization': 'Token '}))
    assert resp.status_code == 401


@pytest.mark.django_db
def test_invalid_token_returns_401():
    @require_pretix_token
    def view(req):
        return JsonResponse({'ok': True})

    resp = view(_request(headers={'Authorization': 'Token nonexistent123'}))
    assert resp.status_code == 401


def test_noop_auth_allows_all():
    """noop_auth bypasses auth — used in tests via monkeypatch."""
    @noop_auth
    def view(req):
        return JsonResponse({'ok': True})

    resp = view(_request())
    assert resp.status_code == 200
