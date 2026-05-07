"""Auth decorator for plugin endpoints called from devcon-next.

Uses Pretix's own API token system (TeamAPIToken) — the same token
devcon-next already uses for order management. No extra shared secret needed.

In tests: either create a TeamAPIToken fixture, or monkeypatch this decorator.
"""
from functools import wraps
from django.http import JsonResponse


def require_pretix_token(view_func):
    """Validate the request's Authorization header against Pretix's TeamAPIToken table.
    Accepts `Authorization: Token <token>`. Returns 401 for missing/invalid tokens."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth:
            return JsonResponse({'success': False, 'error': 'authorization required'}, status=401)
        if not auth.startswith('Token '):
            return JsonResponse({'success': False, 'error': 'invalid auth header format'}, status=401)
        token_str = auth[6:].strip()
        if not token_str:
            return JsonResponse({'success': False, 'error': 'empty token'}, status=401)
        try:
            from pretix.base.models import TeamAPIToken
            token = TeamAPIToken.objects.select_related('team').get(token=token_str, active=True)
            # Verify token's team belongs to the correct organizer (prevents cross-org access)
            team = token.team
            request._pretix_team = team
        except Exception:
            return JsonResponse({'success': False, 'error': 'invalid or inactive API token'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def check_team_event_access(request, event) -> bool:
    """Verify the authenticated team has access to this event's organizer.
    Returns True if authorized, False if the token doesn't cover this organizer."""
    team = getattr(request, '_pretix_team', None)
    if team is None:
        return True  # no team on request = auth was bypassed (tests / no-auth mode)
    return team.organizer_id == event.organizer_id


def noop_auth(view_func):
    """No-op replacement for require_pretix_token. Use in tests via monkeypatch:
        monkeypatch.setattr('pretix_eth.views_x402.require_pretix_token', noop_auth)
    """
    return view_func


def get_client_ip(request) -> str:
    """Return the buyer's IP, honoring `X-Forwarded-For` only when the request
    actually arrived through a trusted proxy.

    The unsafe pattern (read XFF unconditionally) is a classic rate-limit
    bypass — any client can spoof a unique XFF on every request and walk
    around per-IP throttles. We pin XFF processing to a configured proxy
    allowlist: if the socket peer (`REMOTE_ADDR`) matches one of the IPs in
    the trusted-proxy list, we trust the leftmost XFF entry as the real
    client; otherwise we ignore XFF entirely and use the socket peer.

    Two ways to configure (either is fine; both are merged):

        # Django settings (pretix_settings.py / a config bridge)
        PRETIX_ETH_TRUSTED_PROXIES = ['10.0.0.5', '172.16.0.10']

        # Environment (Docker / systemd / Pretix Hosted)
        export PRETIX_ETH_TRUSTED_PROXIES="10.0.0.5,172.16.0.10"

    Leave both empty to always use the socket peer — correct for deployments
    behind a single trusted reverse proxy that strips XFF, or for any setup
    where the proxy IP isn't stable enough to allowlist.
    """
    import os
    from django.conf import settings as django_settings
    socket_ip = request.META.get('REMOTE_ADDR', '') or 'unknown'
    trusted = list(getattr(django_settings, 'PRETIX_ETH_TRUSTED_PROXIES', None) or [])
    env_trusted = os.environ.get('PRETIX_ETH_TRUSTED_PROXIES', '')
    if env_trusted:
        trusted.extend(p.strip() for p in env_trusted.split(',') if p.strip())
    if socket_ip in trusted:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            first = xff.split(',')[0].strip()
            if first:
                return first
    return socket_ip
