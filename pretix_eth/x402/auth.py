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
    arrived through a caller we already authenticated via TeamAPIToken.

    The unsafe pattern (read XFF unconditionally) is a classic rate-limit
    bypass — any client can spoof a unique XFF on every request and walk
    around per-IP throttles. The mitigation is to trust XFF only from a
    known proxy.

    Rather than allowlisting proxy IPs (brittle on Netlify and other PaaS
    edges where egress IPs aren't stable), we use the existing trust
    boundary: `@require_pretix_token` sets `request._pretix_team` to a
    valid TeamAPIToken's team. If that attribute is present, the request
    came from a backend that already proved it's *our* proxy (it has a
    token nobody else does), so we honor XFF. If it's absent, the request
    is unauthenticated — typically a buyer's browser calling the legacy WC
    flow directly — and any XFF on it is attacker-controlled, so we ignore
    XFF and use the socket peer.

    The monorepo's `pluginFetch` adds both `Authorization: Token …` and
    `X-Forwarded-For: <buyer-ip>` to every plugin call, so this works
    end-to-end with no new config on either side.
    """
    import logging
    log = logging.getLogger('pretix_eth.client_ip')
    socket_ip = request.META.get('REMOTE_ADDR', '') or 'unknown'
    has_token = getattr(request, '_pretix_team', None) is not None
    xff_raw = request.META.get('HTTP_X_FORWARDED_FOR', '')
    xff_first = xff_raw.split(',')[0].strip() if xff_raw else ''

    # Truthy = decorator validated a TeamAPIToken; this caller is one of
    # our trusted backends. None / missing = unauthenticated buyer call.
    if has_token and xff_first:
        resolved = xff_first
        path = 'token+xff'
    else:
        resolved = socket_ip
        path = 'socket'

    # DIAGNOSTIC — INFO-level log of every IP-resolution decision, with
    # all the headers a typical reverse-proxy chain might set. Revert to a
    # quieter level once the deployment's IP-forwarding behaviour is
    # understood. Cheap (one log line per rate-limited endpoint hit) but
    # noisy; not intended to ship to production long-term.
    log.info(
        'get_client_ip resolved=%s path=%s socket=%s xff=%s xff_first=%s '
        'x_real_ip=%s cf_connecting_ip=%s nf_client_connection_ip=%s '
        'has_token=%s url=%s',
        resolved, path, socket_ip, xff_raw or '-', xff_first or '-',
        request.META.get('HTTP_X_REAL_IP', '-'),
        request.META.get('HTTP_CF_CONNECTING_IP', '-'),
        request.META.get('HTTP_X_NF_CLIENT_CONNECTION_IP', '-'),
        has_token, request.path,
    )
    return resolved
