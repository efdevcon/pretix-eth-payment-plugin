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
                    {'success': False, 'error': 'forbidden — token does not cover this event'},
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
    """Verify the authenticated team has access to THIS event, matching Pretix
    core's REST authz (CVE-2026-5600): organizer membership AND event scope.

    V76: this previously checked organizer membership ONLY, ignoring
    `Team.all_events` / `Team.limit_events`. That let a token legitimately
    scoped to a single event drive the money-moving /plugin/admin/* tools
    (admin_wc_verify, admin_refund, admin_wc_refund) against any sibling event
    under the same organizer. Core's REST layer honors limit_events, so the
    plugin must too or the core CVE fix doesn't extend to this surface.

    Returns True if authorized, False otherwise."""
    team = getattr(request, '_pretix_team', None)
    if team is None:
        return True  # no team on request = auth was bypassed (tests / no-auth mode)
    if team.organizer_id != event.organizer_id:
        return False
    if getattr(team, 'all_events', False):
        return True
    try:
        return team.limit_events.filter(pk=event.pk).exists()
    except Exception:
        return False


def noop_auth(view_func):
    """No-op replacement for require_pretix_token. Use in tests via monkeypatch:
        monkeypatch.setattr('pretix_eth.views_x402.require_pretix_token', noop_auth)
    """
    return view_func


def get_client_ip(request) -> str:
    """Return the buyer's IP for per-IP rate limiting.

    Two trust paths:

    1) Token-authenticated callers (our Next.js proxy, `has_token=True`):
       prefer the `X-Pretix-Buyer-Ip` header `pluginFetch` injects, then
       its `X-Forwarded-For`. These are trustworthy because the caller
       proved it's our backend by presenting a valid TeamAPIToken.

    2) Direct buyer-browser calls to `/plugin/wc/*` (`has_token=False`):
       these come THROUGH Cloudflare (our known front edge), which sets
       `CF-Connecting-IP` and normalizes `X-Real-IP` / `X-Forwarded-For`.
       We trust those, in that order, falling back to the socket peer.

    Why this is safe — and why the previous "socket-only for tokenless"
    rule was actively harmful: behind the Cloudflare → host chain the
    socket peer (`REMOTE_ADDR`) is empty, so every buyer resolved to the
    literal string 'unknown'. That collapsed ALL buyers into a single
    shared rate-limit bucket — the per-IP limit wasn't per-IP at all, and
    at launch the whole event's verify polls summed into one bucket and
    tripped the limit almost immediately (see the launch retro: every
    `rate limit exceeded (ip)` rejection logged `ip=unknown`).

    The spoofing concern that motivated socket-only is real but moot here:
    an attacker who can forge `CF-Connecting-IP`/`X-Real-IP` would have to
    reach the origin *bypassing Cloudflare*. If the origin is locked to
    Cloudflare's ranges (infra-level), these headers can't be forged; if
    it isn't, the attacker could already evade the limit (and the old
    behavior gave them an unlimited shared bucket anyway). Trusting CF's
    headers strictly improves fairness for legitimate buyers.
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
    # Cloudflare-set headers for direct buyer calls. `CF-Connecting-IP` is
    # CF's canonical client-IP header (overwrites any client value);
    # `X-Real-IP` is what the host proxy populates in this deployment (the
    # launch logs showed it carrying the real IP while CF-Connecting-IP was
    # absent), so we keep it as a fallback.
    cf_connecting_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
    x_real_ip = request.META.get('HTTP_X_REAL_IP', '').strip()

    # Truthy = decorator validated a TeamAPIToken; this caller is one of
    # our trusted backends. None / missing = unauthenticated buyer call.
    if has_token and pretix_buyer_ip:
        resolved = pretix_buyer_ip
        path = 'token+pretix_buyer_ip'
    elif has_token and xff_first:
        resolved = xff_first
        path = 'token+xff'
    elif cf_connecting_ip:
        resolved = cf_connecting_ip
        path = 'cf_connecting_ip'
    elif x_real_ip:
        resolved = x_real_ip
        path = 'x_real_ip'
    elif xff_first:
        resolved = xff_first
        path = 'xff'
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
