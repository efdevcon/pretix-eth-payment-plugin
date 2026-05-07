"""Auth decorator for plugin endpoints called from devcon-next.

Uses Pretix's own API token system (TeamAPIToken) — the same token
devcon-next already uses for order management. No extra shared secret needed.

In tests: either create a TeamAPIToken fixture, or monkeypatch this decorator.
"""
import json
from functools import wraps
from django.http import JsonResponse


def _resolve_event_from_request(request):
    """Best-effort lookup of the (organizer, event) the request targets.

    Reads `?organizer=…&event=…` from the URL and falls back to top-level
    JSON body fields. Returns the Event or None. Used by the auth decorators
    to enforce that the authenticated team has access to the URL's event,
    closing the V1/V1.b cross-tenant authorization holes.
    """
    org_slug = request.GET.get('organizer') or ''
    event_slug = request.GET.get('event') or ''
    if not (org_slug and event_slug):
        try:
            body = json.loads(request.body or b'{}')
            if isinstance(body, dict):
                org_slug = org_slug or body.get('organizer', '') or ''
                event_slug = event_slug or body.get('event', '') or ''
        except json.JSONDecodeError:
            pass
    if not (org_slug and event_slug):
        return None
    try:
        from pretix.base.models import Event
        from django_scopes import scopes_disabled
        with scopes_disabled():
            return Event.objects.filter(
                slug=event_slug, organizer__slug=org_slug,
            ).select_related('organizer').first()
    except Exception:
        return None


def _validate_token(request):
    """Internal: parse Authorization header, validate against TeamAPIToken,
    set `request._pretix_team`. Returns (None, None) on success or
    (status_code, error_message) on failure."""
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth:
        return 401, 'authorization required'
    if not auth.startswith('Token '):
        return 401, 'invalid auth header format'
    token_str = auth[6:].strip()
    if not token_str:
        return 401, 'empty token'
    try:
        from pretix.base.models import TeamAPIToken
        token = TeamAPIToken.objects.select_related('team').get(token=token_str, active=True)
        request._pretix_team = token.team
    except Exception:
        return 401, 'invalid or inactive API token'
    return None, None


def require_pretix_token(view_func):
    """Validate the request's Authorization header against Pretix's TeamAPIToken table.
    Accepts `Authorization: Token <token>`. Returns 401 for missing/invalid tokens.

    V1 hardening: also enforces that the authenticated team has access to
    the (organizer, event) the request targets. If the request includes
    organizer+event in either the query string or JSON body and the resolved
    Event is owned by a different organizer than the token's team, returns
    403 — preventing a token from one organizer being used to operate on
    another organizer's events.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        status, err = _validate_token(request)
        if status is not None:
            return JsonResponse({'success': False, 'error': err}, status=status)
        # V1 cross-tenant check: when the request names a specific event,
        # confirm the token's team is in that event's organizer.
        event = _resolve_event_from_request(request)
        if event is not None and not check_team_event_access(request, event):
            return JsonResponse(
                {'success': False, 'error': 'forbidden — token does not cover this organizer'},
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def require_pretix_admin_token(perm):
    """Stricter variant of `require_pretix_token` for admin endpoints.

    On top of the basic token + cross-tenant check, requires the
    authenticated team to have a specific Pretix permission flag enabled
    (e.g. `can_view_orders`, `can_change_orders`). This closes V1.b — a
    legitimate buyer-facing token that happens to be in the same organizer
    can't be used to call `/admin/refund/` if its team only has
    view-level permissions.

    Use as `@require_pretix_admin_token('can_change_orders')` etc.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            status, err = _validate_token(request)
            if status is not None:
                return JsonResponse({'success': False, 'error': err}, status=status)
            event = _resolve_event_from_request(request)
            if event is not None and not check_team_event_access(request, event):
                return JsonResponse(
                    {'success': False, 'error': 'forbidden — token does not cover this organizer'},
                    status=403,
                )
            team = getattr(request, '_pretix_team', None)
            # team is always set if _validate_token succeeded; the getattr
            # is defensive in case a test monkeypatches the validator.
            if team is None or not getattr(team, perm, False):
                return JsonResponse(
                    {'success': False, 'error': f'forbidden — token lacks {perm}'},
                    status=403,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


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
    # Custom header set by `pluginFetch` so we can carry the buyer IP through
    # Cloudflare (which overwrites the standard `X-Forwarded-For`). Read this
    # FIRST for token-authenticated traffic — it's the only header that
    # actually survives an end-to-end Netlify → CF → pretix chain.
    pretix_buyer_ip = request.META.get('HTTP_X_PRETIX_BUYER_IP', '').strip()
    xff_raw = request.META.get('HTTP_X_FORWARDED_FOR', '')
    xff_first = xff_raw.split(',')[0].strip() if xff_raw else ''

    # Truthy = decorator validated a TeamAPIToken; this caller is one of
    # our trusted backends. None / missing = unauthenticated buyer call.
    if has_token and pretix_buyer_ip:
        resolved = pretix_buyer_ip
        path = 'token+pretix_buyer_ip'
    elif has_token and xff_first:
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
        'get_client_ip resolved=%s path=%s socket=%s pretix_buyer_ip=%s '
        'xff=%s xff_first=%s x_real_ip=%s cf_connecting_ip=%s '
        'nf_client_connection_ip=%s has_token=%s url=%s',
        resolved, path, socket_ip, pretix_buyer_ip or '-',
        xff_raw or '-', xff_first or '-',
        request.META.get('HTTP_X_REAL_IP', '-'),
        request.META.get('HTTP_CF_CONNECTING_IP', '-'),
        request.META.get('HTTP_X_NF_CLIENT_CONNECTION_IP', '-'),
        has_token, request.path,
    )
    return resolved
