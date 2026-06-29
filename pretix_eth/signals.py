from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.html import format_html

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.base.models import OrderFee
from pretix.presale.signals import html_head, process_response
from pretix.base.signals import register_payment_providers, register_text_placeholders
from pretix.base.services.placeholders import SimpleFunctionalTextPlaceholder


@receiver(process_response, dispatch_uid='wc_checkout_csp')
def add_wc_csp(sender, request, response, **kwargs):
    """Inject CSP directives needed for WalletConnect, AppKit, Alchemy RPC, and public RPCs."""
    h = {}
    if 'Content-Security-Policy' in response:
        h = _parse_csp(response['Content-Security-Policy'])
    _merge_csp(h, {
        'style-src': ["'unsafe-inline'"],
        'img-src': [
            'blob: data:',
            'https://*.walletconnect.com',
            'https://*.reown.com',
        ],
        'script-src': [
            "'unsafe-inline'",
            "'unsafe-eval'",
        ],
        'font-src': [
            'https://fonts.gstatic.com',
            'https://fonts.reown.com',
        ],
        'frame-src': [
            'https://verify.walletconnect.org',
            'https://verify.walletconnect.com',
            'https://*.walletconnect.org',
        ],
        'connect-src': [
            'https://*.walletconnect.org',
            'https://*.walletconnect.com',
            'wss://relay.walletconnect.org',
            'wss://relay.walletconnect.com',
            'wss://*.walletconnect.org',
            'https://pulse.walletconnect.org',
            'https://*.reown.com',
            'https://*.alchemy.com',
            'https://*.publicnode.com',
            'https://api.web3modal.org',
            'https://*.web3modal.org',
            'https://*.coinbase.com',
            # Safe Transaction Service (multisig detection + safeTxHash /
            # safeMessageHash polling). Required only when an event admin
            # opts in via `safe_payments_enabled`; harmless to allowlist
            # globally since the bundle won't call it otherwise.
            'https://*.safe.global',
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response


@receiver(register_payment_providers, dispatch_uid='wc_register_payment')
def register_payment_provider(sender, **kwargs):
    from .payment import WalletConnectPayment
    return WalletConnectPayment


@receiver(register_text_placeholders, dispatch_uid='wc_secret_placeholder')
def register_order_secret_placeholder(sender, **kwargs):
    """Expose `{secret}` as a mail placeholder. Pretix's stock list includes
    `{code}` and `{url}` but not the bare order secret. Useful for operators
    who want to compose URLs inside the email template directly."""
    return SimpleFunctionalTextPlaceholder(
        'secret',
        ['order'],
        lambda order: order.secret,
        sample=lambda event: 'a1b2c3d4e5f6g7h8',
    )


@receiver(register_text_placeholders, dispatch_uid='wc_url_override')
def register_url_override(sender, **kwargs):
    """Override the stock `{url}` placeholder when the operator has configured
    a `frontend_order_url_template` on the WalletConnect plugin settings.

    Pretix's default `{url}` (in `pretix.base.services.placeholders`) builds
    a presale self-service order URL on Pretix's own domain. Operators
    running a separate FE (devcon-next) want emails to link into the FE's
    order page instead. Last-write-wins on placeholder identifier — plugin
    signals are dispatched after core, so our `{url}` shadows the default
    when this setting is non-empty.

    The template supports `{code}` and `{secret}` substitution. Example:
        https://devcon.org/en/tickets/store/order/{code}/{secret}/
    """
    from .payment import WalletConnectPayment
    provider = WalletConnectPayment(sender)
    template = (provider.settings.get('frontend_order_url_template') or '').strip()
    if not template:
        return []  # no override → Pretix default `{url}` wins
    return SimpleFunctionalTextPlaceholder(
        'url',
        ['order', 'event'],
        lambda order, event: (
            template.replace('{code}', order.code).replace('{secret}', order.secret)
        ),
        sample=lambda event: (
            template.replace('{code}', 'CODEX1').replace('{secret}', 'a1b2c3d4e5f6g7h8')
        ),
    )


@receiver(register_text_placeholders, dispatch_uid='wc_pretix_url_placeholder')
def register_pretix_url_placeholder(sender, **kwargs):
    """Register a `{pretix_url}` placeholder that always resolves to the
    Pretix-native order URL (e.g. https://dcdev2.ticketh.xyz/<org>/<event>/
    order/<code>/<secret>/), regardless of whether `{url}` is overridden
    to point at the storefront/frontend (devcon.org).

    Use case: emails that link to the storefront via `{url}` (for the
    buyer's primary action) AND want a separate "view on Pretix" link
    (admin-style fallback, raw invoice download, etc.) need a
    placeholder that doesn't follow the override.

    Pretix doesn't ship `{pretix_url}` natively — this is plugin-provided.
    The same placeholder applies to every payment method (crypto, Stripe,
    bank transfer, etc.) since it just resolves an event-relative URL.
    """
    from pretix.multidomain.urlreverse import build_absolute_uri
    return SimpleFunctionalTextPlaceholder(
        'pretix_url',
        ['order', 'event'],
        lambda order, event: build_absolute_uri(
            event, 'presale:event.order',
            kwargs={'order': order.code, 'secret': order.secret},
        ),
        sample=lambda event: build_absolute_uri(
            event, 'presale:event.order',
            kwargs={'order': 'CODEX1', 'secret': 'a1b2c3d4e5f6g7h8'},
        ),
    )


try:
    from pretix.base.signals import periodic_task

    @receiver(periodic_task, dispatch_uid='pretix_eth_x402_cleanup')
    def register_x402_cleanup(sender, **kwargs):
        # Runs every hour via Pretix's built-in periodic_task signal
        from pretix_eth.x402.tasks import cleanup_expired_pending_task, cleanup_verify_attempts_task
        cleanup_expired_pending_task.apply_async()
        cleanup_verify_attempts_task.apply_async()
except ImportError:
    # Fallback: no periodic scheduling (dev/test environments)
    pass


@receiver(html_head, dispatch_uid='wc_order_redirect_inject')
def inject_order_redirect(sender, request, **kwargs):
    """Inject a `<script>` on Pretix's order-detail page that redirects
    the buyer to the operator's configured frontend order URL after a
    short delay. Same UX as the wc_inject SuccessStep does for crypto
    orders, extended here to every payment provider (Stripe, bank
    transfer, etc.) — Pretix's stock order page is the post-payment
    landing for non-crypto orders, so the redirect happens here instead.

    Guards:
      - URL must be the order detail page (`event.order`), not a
        sub-page like `event.order.pay`, `event.order.cancel`, etc.,
        where the buyer still has work to do on Pretix.
      - The order must be PAID — pending/expired orders shouldn't be
        redirected away from Pretix where the buyer needs to act.
      - `frontend_order_url_template` must be configured on the event.

    The actual JS lives at a plugin URL (`order_redirect_js` view) so
    it loads from `'self'` — Pretix's presale CSP blocks inline
    `<script>` blocks.

    The script itself uses `sessionStorage` to redirect at most once per
    browser session per order, so a buyer who bookmarks the Pretix URL
    and revisits later isn't redirected away again.
    """
    import logging
    log = logging.getLogger(__name__)
    match = getattr(request, 'resolver_match', None)
    url_name = (match.url_name or '') if match else '<no-match>'
    if url_name != 'event.order':
        return ''
    code = match.kwargs.get('order')
    secret = match.kwargs.get('secret')
    if not code or not secret:
        return ''
    log.info(
        'pretix_eth[redirect]: html_head fired url_name=%s code=%s thanks=%s',
        url_name, code, request.GET.get('thanks'),
    )

    # Quick read of the template setting — skip rendering entirely when
    # the operator hasn't configured a redirect target.
    template = (sender.settings.get('payment_walletconnect_frontend_order_url_template') or '').strip()
    if not template:
        return ''

    # Redirect ONLY on the just-paid landing where Pretix appends
    # `?thanks=yes` (set by the post-payment redirect from
    # `/pay/<id>/complete` → `/order/<code>/<secret>/?thanks=yes`).
    # Buyers who revisit their order via the email link or a bookmark
    # later shouldn't be bounced to the storefront — they expect the
    # Pretix order page to actually load (e.g. to view ticket details
    # or download an invoice). The `?thanks=yes` flag is the only
    # signal that distinguishes "just paid, take me to the next page"
    # from "I navigated here on purpose."
    if request.GET.get('thanks') != 'yes':
        return ''

    try:
        from pretix.multidomain.urlreverse import eventreverse
        url = eventreverse(sender, 'plugins:pretix_eth:wc_order_redirect_js')
    except Exception:
        return ''

    return format_html(
        '<script src="{}?code={}&secret={}"></script>',
        url, code, secret,
    )


@receiver(html_head, dispatch_uid='wc_item_pricing_inject')
def inject_item_pricing(sender, request, **kwargs):
    """Inject the buyer-side dual-price rendering script on Pretix's
    catalog and cart pages.

    The script (served by `views.item_pricing_js`) fetches the event's
    item-pricing JSON and DOM-annotates each item row with a "Card: $X"
    hint or a "Crypto only" badge. Loading it via an `html_head` signal
    keeps the injection scoped to event-buyer pages — admin pages and
    other organizer surfaces are unaffected.

    URL-name allowlist:
      - `event.index` — main catalog (item list + optional cart sidebar)
      - `event.checkout` / `event.checkout.*` — checkout funnel steps
      - `event.cart.*` — cart manipulation routes (cart preview, add, etc.)

    Deliberately NOT injected on `event.order.*`. Once an order exists,
    the buyer has either already paid (showing "Card: $999" hints next
    to items they paid $499 for in ETH would be confusing) or is about
    to pay against a fixed Pretix-computed total (the order's actual
    `OrderFee` row already captures the fiat markup, so dual-price hints
    would just duplicate it). Dual-price rendering belongs in the
    pre-commitment surfaces only.
    """
    match = getattr(request, 'resolver_match', None)
    url_name = (match.url_name or '') if match else ''
    if not url_name:
        return ''
    allowed_prefixes = (
        'event.index',
        'event.checkout',
        'event.cart',
    )
    if not any(url_name == p or url_name.startswith(p + '.') for p in allowed_prefixes):
        return ''
    try:
        from pretix.multidomain.urlreverse import eventreverse
        url = eventreverse(sender, 'plugins:pretix_eth:wc_item_pricing_js')
    except Exception:
        return ''
    return format_html('<script src="{}"></script>', url)


@receiver(pre_save, sender=OrderFee, dispatch_uid='wc_stripe_fee_label')
def set_stripe_fee_label(sender, instance, **kwargs):
    """Set OrderFee.description on Stripe payment fees so the line shown
    on the order page, invoice PDF, and confirmation emails reads
    'Credit card processing fee ($500)' instead of Pretix's generic
    'Payment fee' fallback.

    The dollar amount is read from `instance.value` (the actual fee on
    the order), so the label matches the per-item markup the buyer paid.

    Skipped when:
      - The fee is not a payment fee (FEE_TYPE_PAYMENT)
      - The provider is not a Stripe variant (`stripe`, `stripe_cc`, ...)
      - A description is already set (admin edit or earlier hook wins)
      - The fee value is 0 or unset

    Only affects newly created/saved fees. Existing OrderFee rows keep
    their current description until they get saved again; a one-off
    backfill via the Django shell can update historical rows if needed.
    """
    if instance.fee_type != OrderFee.FEE_TYPE_PAYMENT:
        return
    if not (instance.internal_type or '').startswith('stripe'):
        return
    if instance.description:
        return
    from decimal import Decimal
    try:
        value = instance.value if isinstance(instance.value, Decimal) else Decimal(str(instance.value or 0))
    except Exception:
        return
    if value <= 0:
        return  # no markup on this order; leave the default 'Payment fee' label
    try:
        currency = (instance.order.event.currency or 'USD').strip() or 'USD'
    except Exception:
        currency = 'USD'
    # Strip trailing zeros so 500.00 displays as 500, 12.50 stays 12.50.
    if value == value.to_integral():
        num = format(value.normalize(), 'f')
    else:
        num = format(value, 'f').rstrip('0').rstrip('.')
    amount_str = f'${num}' if currency == 'USD' else f'{num} {currency}'.strip()
    instance.description = f'Credit card processing fee ({amount_str})'
