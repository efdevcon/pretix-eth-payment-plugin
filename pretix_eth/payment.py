"""Pretix payment provider for WalletConnect-based crypto checkout."""
import logging
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.conf import settings as dj_settings
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from pretix.base.payment import BasePaymentProvider

from pretix_eth.chains import SUPPORTED_CHAINS, ALL_SYMBOLS, CHAIN_METADATA

log = logging.getLogger(__name__)


def _read_discount_pct(settings) -> Decimal:
    """Normalise `crypto_discount_percent` to a `Decimal`. Returns Decimal('0')
    for every representation of "disabled":
      - missing / never-set                  → '0'
      - explicit None (form was cleared)     → '0'
      - empty string                         → '0'
      - explicit "0" / "0.00" / Decimal(0)   → '0'
      - anything that doesn't parse cleanly  → '0' (defensive)
    Anything > 0 is returned as-is.

    `provider.settings.get(..., as_type=Decimal)` mostly handles the None / empty
    cases, but Pretix versions vary; this helper is the single chokepoint for
    "what does the percent actually evaluate to right now" so every consumer
    reaches the same answer."""
    raw = settings.get('crypto_discount_percent', default=None)
    if raw is None or raw == '':
        return Decimal('0')
    try:
        return Decimal(str(raw))
    except Exception:
        return Decimal('0')


def _format_crypto_amount(raw, token_symbol):
    """Convert a stored raw on-chain integer (USDC/USDT0 in 6-decimal base units,
    ETH in wei) into a human-readable decimal string. Returns None on bad input
    so the Pretix control template can omit the row entirely.

    Legacy quirk: historical rows from `views.py` stored `"<int> (raw)"` — strip
    the suffix before parsing so those display correctly without a DB backfill."""
    if raw in (None, ''):
        return None
    decimals = 18 if token_symbol == 'ETH' else 6
    # Tolerate the legacy "<int> (raw)" format written by views.py prior to fix.
    s = str(raw).strip()
    if s.endswith('(raw)'):
        s = s[:-len('(raw)')].strip()
    try:
        n = int(s)
    except (TypeError, ValueError):
        return str(raw)  # fall back to raw value for forward-compat
    if n == 0:
        return '0'
    base = 10 ** decimals
    whole, frac = divmod(n, base)
    if frac == 0:
        return str(whole)
    frac_str = f'{frac:0{decimals}d}'.rstrip('0')
    return f'{whole}.{frac_str}'


_SYMBOL_DISPLAY = {'USDT0': 'USD₮0'}


def _english_list(items):
    """Format ['ETH', 'USDC', 'USDT0'] as 'ETH, USDC, or USD₮0'. Display
    symbols (`USDT0 → USD₮0`) are applied here so callers don't have to
    remember. Falls back gracefully for 0/1/2-element lists."""
    xs = [_SYMBOL_DISPLAY.get(s, s) for s in items]
    if not xs:
        return ''
    if len(xs) == 1:
        return xs[0]
    if len(xs) == 2:
        return '{} or {}'.format(*xs)
    return '{}, or {}'.format(', '.join(xs[:-1]), xs[-1])


class WalletConnectPayment(BasePaymentProvider):
    identifier = 'walletconnect'
    verbose_name = _('Ethereum payment')
    abort_pending_allowed = True

    def _enabled_symbols(self):
        """Symbols this event has actually enabled, in canonical display
        order (ETH → USDC → USDT0). Drives public_name and the
        pre-confirm template — both stay in sync with operator toggles."""
        order = ('ETH', 'USDC', 'USDT0')
        return [
            sym for sym in order
            if sym in ALL_SYMBOLS
            and str(self.settings.get(f'token_{sym}', default='True')).lower() in ('true', '1', 'yes')
        ]

    def _enabled_chain_ids(self):
        """Chain IDs this event has enabled. Same shape as `_enabled_symbols`
        — operator toggle = single source of truth."""
        return [
            cid for cid in SUPPORTED_CHAINS
            if str(self.settings.get(f'chain_{cid}', default='True')).lower() in ('true', '1', 'yes')
        ]

    @property
    def public_name(self):
        # Buyer-facing name in Pretix's checkout method picker. Reflects
        # only the tokens this event has enabled — never lists USDC if
        # the operator turned it off. Appends "— N% Discount" when a
        # crypto discount is active so the negative-fee amount Pretix
        # shows next to the row reads as a benefit, not a charge.
        symbols = self._enabled_symbols()
        chain_ids = self._enabled_chain_ids()
        # Special case: ETH on mainnet only (L1 wave-launch flow). Render
        # the chain explicitly so the buyer doesn't wonder which network
        # the bare "Crypto (ETH)" label refers to.
        if symbols == ['ETH'] and chain_ids == [1]:
            base = _('ETH on Mainnet (L1)')
        elif not symbols:
            base = _('Crypto')
        else:
            base = _('Crypto ({symbols})').format(symbols=_english_list(symbols))
        pct = _read_discount_pct(self.settings)
        if pct <= 0:
            return base
        # Drop the trailing zeros so 10.00 → 10, 7.50 → 7.5.
        pct_str = format(pct.normalize(), 'f')
        return _('{base} — {pct}% Discount').format(base=base, pct=pct_str)

    def _english_token_list(self) -> str:
        return _english_list(self._enabled_symbols())

    @property
    def settings_form_fields(self):
        base = OrderedDict(list(super().settings_form_fields.items()))
        base['x402_enabled'] = forms.BooleanField(
            label=_('Enable x402 (gasless USDC checkout)'),
            help_text=_(
                'Allow buyers to pay via the x402 flow on this event. '
                'Leave OFF unless the x402 protocol-level controls (relayer '
                'funding, facilitator API key, agent endpoints) have all been '
                'configured for this event. When OFF, the legacy WalletConnect '
                'flow remains available; existing x402 orders can still be '
                'viewed and refunded from the admin panel.'
            ),
            required=False,
            initial=False,
        )
        # Companion gate for the storefront's external-API purchase path.
        # `fiat-purchase.ts` in the monorepo POSTs straight to Pretix's
        # organizer REST `/api/v1/.../orders/` with the merchant API token —
        # bypassing service-layer validation. The storefront polls
        # `/plugin/x402/settings/` and refuses to call fiat-purchase when this
        # toggle is OFF, mooting the M9 stopgap's residual gaps (M18–M22)
        # for v1. Buyer-facing WC and x402 checkout flows are unaffected by
        # this flag.
        base['fiat_purchase_enabled'] = forms.BooleanField(
            label=_('Enable external API purchase (devcon fiat-purchase)'),
            help_text=_(
                'Allow the storefront\'s external API purchase endpoint '
                '(`/api/x402/tickets/fiat-purchase`) to create orders for '
                'this event via Pretix organizer REST. Leave OFF unless '
                'external-API checkout is operationally required. When OFF, '
                'the storefront\'s WC and x402 buyer-facing checkout flows '
                'are unaffected; only the external-API path is blocked.'
            ),
            required=False,
            initial=False,
        )
        # When ON, Pretix's standard "Order Placed" email is suppressed for
        # orders paid via this provider (both buyer and attendee variants).
        # Useful when the crypto checkout resolves in seconds — buyer would
        # otherwise receive placed + paid emails moments apart. Stripe / bank
        # transfer orders still get the placed email; only this provider is
        # short-circuited.
        base['suppress_order_placed_email'] = forms.BooleanField(
            label=_('Suppress "Order Placed" email for crypto orders'),
            help_text=_(
                'When checked, the buyer (and attendee) "Order Placed" emails '
                'are not sent for orders paid via this Ethereum-payment '
                'provider. Crypto orders typically settle within seconds, so '
                'the placed email is redundant with the "Order Paid" one. '
                'Orders paid via Stripe or bank transfer are unaffected.'
            ),
            required=False,
            initial=False,
        )
        # wc_inject's Safe-multisig support is opt-in per event. When ON, the
        # bundle un-excludes Safe from the AppKit picker, detects Safes via
        # Safe Transaction Service at connect time, surfaces a multi-signer
        # notice, polls safeTxHash → on-chain hash after the payment is
        # signed, and polls safeMessageHash → preparedSignature for the
        # challenge sign on multi-sig Safes (ERC-1271). Default OFF so an
        # operator who doesn't have Safe operationally validated for their
        # event doesn't accidentally surface a "stuck-order" path.
        base['safe_payments_enabled'] = forms.BooleanField(
            label=_('Enable Safe (multisig) payments in wc_inject'),
            help_text=_(
                'Surface Safe / Safe-Apps as a connection option in the '
                'on-Pretix crypto checkout, with safeTxHash polling and a '
                'multi-signer notice. Leave OFF unless this event has '
                'validated Safe payments end-to-end — multi-sig Safes can '
                'take minutes to hours for co-signers to approve, so the '
                'order stays in "verifying" the whole time.'
            ),
            required=False,
            initial=False,
        )
        base['receive_address'] = forms.CharField(
            label=_('wc_inject recipient (EIP-55)'),
            help_text=_('Wallet that receives wc_inject (in-Pretix WalletConnect) payments. Should match the x402 recipient below.'),
            max_length=42, min_length=42, required=True,
        )
        base['wc_project_id'] = forms.CharField(
            label=_('WalletConnect project ID (from cloud.reown.com)'),
            required=True,
        )
        base['alchemy_api_key'] = forms.CharField(
            label=_('Alchemy API key (optional; overridden by WC_ALCHEMY_API_KEY env)'),
            required=False,
            widget=forms.PasswordInput(render_value=True),
        )
        base['zapper_api_key'] = forms.CharField(
            label=_('Zapper API key (optional)'),
            help_text=_(
                'When set, the payment-options endpoint fetches wallet balances '
                'via Zapper in a single GraphQL call (~200ms) instead of fanning '
                'out RPC eth_calls per chain (~2s). RPC is used automatically as '
                'a fallback if Zapper fails.'
            ),
            required=False,
            widget=forms.PasswordInput(render_value=True),
        )
        base['relayer_private_key'] = forms.CharField(
            label=_('Relayer private key (gasless USDC/USDT0). Overridden by WC_RELAYER_PRIVATE_KEY env.'),
            required=False,
            widget=forms.PasswordInput(render_value=True),
        )
        base['crypto_discount_percent'] = forms.DecimalField(
            label=_('Crypto discount (% off the fiat price)'),
            help_text=_(
                'Percentage taken off the fiat price for buyers who pay in '
                'crypto. Leave blank or set to 0 to disable the discount '
                'entirely — no discount UI, no negative OrderFee, no math. '
                'Range: 0–50%.'
            ),
            # required=False so operators can leave the field blank to mean
            # "no discount". Pre-fix the field was implicitly required
            # (Django's DecimalField default) which blocked saving the
            # settings form when the operator wanted to disable the discount.
            required=False,
            initial=0,
            min_value=0,
            max_value=50,
            decimal_places=2,
        )
        base['payment_recipient'] = forms.CharField(
            label=_('x402 recipient (EIP-55)'),
            help_text=_('Wallet that receives x402 protocol payments (storefront, agent endpoint). Should match the wc_inject recipient above.'),
            max_length=42, min_length=42, required=True,
        )
        # Individual boolean per chain (hierarkey stores bools cleanly)
        for cid in SUPPORTED_CHAINS:
            base[f'chain_{cid}'] = forms.BooleanField(
                label=_('Chain: %s') % CHAIN_METADATA[cid]['name'],
                required=False, initial=True,
            )
        for sym in ALL_SYMBOLS:
            base[f'token_{sym}'] = forms.BooleanField(
                label=_('Token: %s') % sym,
                required=False, initial=True,
            )
        base['quote_ttl_seconds'] = forms.IntegerField(
            label=_('Quote TTL (seconds)'),
            initial=600, min_value=60, max_value=3600,
        )
        base['min_confirmations'] = forms.IntegerField(
            label=_('Minimum confirmations'),
            initial=1, min_value=0, max_value=50,
        )
        base['support_email'] = forms.EmailField(
            label=_('Support email for payment issues'),
            help_text=_(
                'Shown to buyers if their payment gets stuck. Leave blank to hide the '
                'support contact block. Admin-side manual verification is available in the '
                'admin page regardless of this setting.'
            ),
            required=False,
        )
        base['frontend_order_url_template'] = forms.CharField(
            label=_('Frontend order URL template (overrides {url} in emails)'),
            help_text=_(
                'When set, the {url} placeholder in transactional emails (order placed, '
                'paid, etc.) is replaced with this template. Use {code} and {secret} as '
                'substitution tokens. Example: '
                'https://devcon.org/en/tickets/store/order/{code}/{secret}/  — leave '
                'blank to keep the default Pretix self-service URL.'
            ),
            required=False,
        )
        return base

    def calculate_fee(self, price: Decimal) -> Decimal:
        """Apply `crypto_discount_percent` as a negative payment fee on the
        Pretix-native checkout path. Pretix pipes payment-method fees through
        cart/order totals, so a negative return surfaces the discount on the
        confirm step and makes `order.total` (used by quote-build, payment.amount,
        and on-chain verification) reflect it. The x402 path bypasses this:
        it computes its own discounted total and writes it to `order.total`
        directly, so there is no double-application.

        With the form set to `required=False`, the underlying setting can be
        absent, None, or an empty string when the operator disables the
        discount. _read_discount_pct normalises all of those to Decimal('0').
        """
        pct = _read_discount_pct(self.settings)
        if pct <= 0:
            return Decimal('0')
        places = dj_settings.CURRENCY_PLACES.get(self.event.currency, 2)
        return (-price * pct / Decimal('100')).quantize(
            Decimal('1') / 10 ** places, ROUND_HALF_UP
        )

    def is_allowed(self, request=None, total=None):
        return bool(self.settings.get('receive_address')) and bool(self.settings.get('wc_project_id'))

    def checkout_prepare(self, request: HttpRequest, cart):
        return True

    def payment_form_render(self, request: HttpRequest) -> str:
        return ''

    def checkout_confirm_render(self, request: HttpRequest, order=None, info_data=None) -> str:
        if order:
            # Payment retry/continue — order exists, show full crypto checkout UI
            from pretix_eth import __version__ as _plugin_version
            tpl = get_template('pretix_eth/checkout_payment_confirm.html')
            ctx = {
                'wc_project_id': self.settings.get('wc_project_id'),
                'url_prefix': '/plugin/wc',
                'order_code': order.code,
                'order_secret': order.secret,
                # Used by the wc_inject UI to gate insufficient-balance rows
                # in the asset/network picker. Render as a plain decimal
                # string ("12.34") — the bundle parses with parseFloat.
                'order_total_usd': str(order.total),
                # Buyer's email from the Pretix Order — pre-fills the support
                # mailto in the wc UI so the buyer doesn't have to retype it.
                'buyer_email': order.email or '',
                'support_email': self.settings.get('support_email', default='') or '',
                # Same template used for the email `{url}` placeholder
                # (see signals.register_url_override). When set, the
                # wc_inject SuccessStep redirects to the FE order page
                # instead of Pretix's native one — so the post-payment
                # destination matches what we send in the confirmation
                # email. Empty = fall back to Pretix's order page.
                'frontend_order_url_template': (
                    self.settings.get('frontend_order_url_template', default='') or ''
                ),
                # Cache-buster for the bundle + stylesheet. Pretix serves /static/
                # with a long max-age header; without a version query string,
                # mobile browsers (and service workers) serve stale copies of
                # bundle.js/styles.css for days after a plugin update. Bumping
                # __version__ in pretix_eth/__init__.py busts the cache across
                # every client. For dev iteration between version bumps, admins
                # can also force a hard refresh / clear cache.
                'plugin_version': _plugin_version,
                # Single-token / single-chain ETH-on-mainnet wave-launch
                # mode — drives the ConnectStep heading ("Pay with ETH"
                # instead of "Pay with crypto") so the buyer doesn't
                # wonder which network applies.
                'eth_mainnet_only': self._enabled_symbols() == ['ETH'] and self._enabled_chain_ids() == [1],
                # Opt-in flag: see `safe_payments_enabled` field. Bundle
                # reads it to (a) un-exclude Safe from the picker and (b)
                # turn on safeTxHash / safeMessageHash polling. Default OFF.
                'safe_payments_enabled': bool(
                    self.settings.get('safe_payments_enabled', as_type=bool, default=False)
                ),
            }
            return tpl.render(ctx, request=request)
        else:
            # Initial checkout — order not yet created, just confirm payment method.
            # Pass the enabled-token list so the copy reflects this event's actual
            # config (won't list USDC if the operator disabled it).
            tpl = get_template('pretix_eth/checkout_pre_confirm.html')
            return tpl.render({'enabled_tokens': self._english_token_list()}, request=request)

    def payment_is_valid_session(self, request: HttpRequest) -> bool:
        return True

    def execute_payment(self, request: HttpRequest, payment):
        # Redirect directly to the payment confirm page where our React UI loads.
        # This skips the default Pretix flow (thanks page → pay/change → pay/confirm).
        order = payment.order
        org = order.event.organizer.slug
        evt = order.event.slug
        return f'/{org}/{evt}/order/{order.code}/{order.secret}/pay/{payment.pk}/confirm'

    def payment_pending_render(self, request: HttpRequest, payment) -> str:
        tpl = get_template('pretix_eth/pending.html')
        info = payment.info_data or {}
        tx = info.get('tx_hash')
        chain_id = info.get('chain_id')
        explorer = CHAIN_METADATA.get(chain_id, {}).get('explorer_url', '')
        return tpl.render({
            'tx_hash': tx,
            'explorer_url': f'{explorer}{tx}' if tx else None,
        })

    def payment_control_render(self, request: HttpRequest, payment) -> str:
        tpl = get_template('pretix_eth/control.html')
        info = payment.info_data or {}
        # Fall back to the X402CompletedOrder row if the OrderPayment.info_data
        # is missing fields (e.g. historical rows created before we started
        # mirroring amount/token_symbol/block_number into info_data).
        chain_id = info.get('chain_id')
        token_symbol = info.get('token_symbol')
        amount_raw = info.get('amount')
        payer = info.get('payer')
        block_number = info.get('block_number')
        tx_hash = info.get('tx_hash')
        if not all([chain_id, token_symbol, amount_raw, payer]):
            fallback = self._x402_fallback(payment)
            if fallback:
                chain_id = chain_id or fallback.get('chain_id')
                token_symbol = token_symbol or fallback.get('token_symbol')
                amount_raw = amount_raw or fallback.get('amount')
                payer = payer or fallback.get('payer')
                tx_hash = tx_hash or fallback.get('tx_hash')

        # Format the amount. Three cases:
        #   1. We have a raw integer and a token symbol → divide by decimals.
        #   2. No raw value but it's a stablecoin → fall back to payment.amount
        #      (the Pretix OrderPayment amount, stored in event currency), since
        #      USDC/USDT0 are 1:1 with USD. This covers legacy rows that never
        #      had crypto_amount populated.
        #   3. No raw value and not a stable (or unknown token) → omit the row.
        amount_display = _format_crypto_amount(amount_raw, token_symbol)
        if amount_display is None and token_symbol in ('USDC', 'USDT0'):
            try:
                amount_display = str(payment.amount)
            except Exception:
                pass

        explorer = CHAIN_METADATA.get(chain_id, {}).get('explorer_url', '')
        return tpl.render({
            'tx_hash': tx_hash,
            'chain_id': chain_id,
            'chain_name': CHAIN_METADATA.get(chain_id, {}).get('name'),
            'token_symbol': token_symbol,
            'payer': payer,
            'amount': amount_display,
            'block_number': block_number,
            'explorer_url': f'{explorer}{tx_hash}' if tx_hash else None,
        })

    @staticmethod
    def _x402_fallback(payment) -> dict:
        """Look up the matching X402CompletedOrder row (keyed on the Pretix
        order code) so historical OrderPayment rows with thin info_data still
        render usefully. Returns an empty dict when there's no match."""
        try:
            from pretix_eth.models import X402CompletedOrder
            from django_scopes import scopes_disabled
            with scopes_disabled():
                row = X402CompletedOrder.objects.filter(
                    event=payment.order.event, pretix_order_code=payment.order.code,
                ).first()
            if not row:
                return {}
            return {
                'chain_id': row.chain_id,
                'token_symbol': row.token_symbol,
                'amount': row.crypto_amount,
                'payer': row.payer,
                'tx_hash': row.tx_hash,
            }
        except Exception as e:
            log.warning('[x402 render] fallback lookup failed for payment %s: %s', payment.pk, e)
            return {}

    def matching_id(self, payment):
        return (payment.info_data or {}).get('tx_hash')

    def api_payment_details(self, payment) -> dict:
        """Populate the `details` field of payments in Pretix's REST API.
        Without this override, the base class returns `{}` and clients of the
        Pretix REST API (e.g. devcon's order-confirmation page) can't see any
        of the on-chain payment data we stored on `info_data`.
        Falls back to the X402CompletedOrder row for missing fields, same as
        the control-panel renderer."""
        info = payment.info_data or {}
        chain_id = info.get('chain_id')
        token_symbol = info.get('token_symbol')
        amount = info.get('amount')
        payer = info.get('payer')
        tx_hash = info.get('tx_hash')
        if not all([chain_id, token_symbol, amount, payer, tx_hash]):
            fallback = self._x402_fallback(payment)
            if fallback:
                chain_id = chain_id or fallback.get('chain_id')
                token_symbol = token_symbol or fallback.get('token_symbol')
                amount = amount or fallback.get('amount')
                payer = payer or fallback.get('payer')
                tx_hash = tx_hash or fallback.get('tx_hash')
        return {
            'tx_hash': tx_hash,
            'chain_id': chain_id,
            'token_symbol': token_symbol,
            'token_address': info.get('token_address'),
            'amount': amount,
            'payer': payer,
            'payment_reference': info.get('payment_reference'),
            'block_number': info.get('block_number'),
        }

    def api_refund_details(self, refund) -> dict:
        """Populate the `details` field of refunds in Pretix's REST API.
        Same shape contract as `api_payment_details` — Pretix's
        `OrderRefundSerializer.details` calls `provider.api_refund_details`
        (see pretix/api/serializers/order.py:`RefundDetailsField`), and
        the default implementation on `BasePaymentProvider` returns `{}`.
        Without this override, the on-chain refund tx hash + chain id
        that the plugin writes into `OrderRefund.info` via
        `record_pretix_refund` is invisible to any REST API consumer
        (devcon's buyer recap page in particular). The plugin's native
        UI already reads from `info_data` directly, so it's unaffected
        either way."""
        info = refund.info_data or {}
        return {
            'refund_tx_hash': info.get('refund_tx_hash'),
            'chain_id': info.get('chain_id'),
        }

    def order_pending_mail_render(self, order, payment) -> str:
        """Insert a crypto-payment recap into Pretix's order confirmation mail
        (the `{payment_info}` placeholder in the email template). Matches the
        reference pretix-x402-payment plugin's shape, formatted via our helpers
        so amounts display in human-readable decimals."""
        info = payment.info_data or {}
        chain_id = info.get('chain_id')
        token_symbol = info.get('token_symbol')
        amount_raw = info.get('amount')
        payer = info.get('payer')
        tx_hash = info.get('tx_hash')
        # Fall back to the X402CompletedOrder row for any field missing on
        # OrderPayment.info_data (same defensive read used by the control panel
        # renderer — covers historical rows and wc_inject rows that didn't
        # mirror every field).
        if not all([chain_id, token_symbol, amount_raw, payer, tx_hash]):
            fallback = self._x402_fallback(payment)
            if fallback:
                chain_id = chain_id or fallback.get('chain_id')
                token_symbol = token_symbol or fallback.get('token_symbol')
                amount_raw = amount_raw or fallback.get('amount')
                payer = payer or fallback.get('payer')
                tx_hash = tx_hash or fallback.get('tx_hash')
        if not any([chain_id, token_symbol, amount_raw, tx_hash]):
            return ''
        # Stablecoins are 1:1 USD — fall back to payment.amount if we never
        # recorded crypto_amount (historical rows), same logic as the control
        # panel renderer.
        amount_display = _format_crypto_amount(amount_raw, token_symbol)
        if amount_display is None and token_symbol in ('USDC', 'USDT0'):
            try:
                amount_display = str(payment.amount)
            except Exception:
                pass
        # Build the recap directly — the `{payment_info}` placeholder in the
        # order-paid email is processed through `markdown_compile_email`, which
        # collapses single newlines. Using `\n\n` (paragraph break) between
        # fields is what makes them render as separate lines in both the HTML
        # and plain-text email versions.
        explorer = CHAIN_METADATA.get(chain_id, {}).get('explorer_url', '')
        chain_name = CHAIN_METADATA.get(chain_id, {}).get('name')
        tx_url = f'{explorer}{tx_hash}' if tx_hash and explorer else None

        lines: list = []
        if amount_display:
            line = (
                f'Amount: {amount_display} {token_symbol}' if token_symbol
                else f'Amount: {amount_display}'
            )
            # For ETH, append the order-currency equivalent so the buyer
            # sees the dollar value alongside the wei-precise figure.
            # `payment.amount` is the Pretix OrderPayment amount, recorded
            # in the event's currency at order-create time — exactly what
            # the buyer was charged. Stables (USDC, USDT0) are 1:1 USD so
            # the token amount already conveys the dollar value; no extra
            # line needed for them.
            #
            # Format mirrors the buyer-facing order recap on the storefront
            # (`0.00000473 ETH ($0.01)`) — symbol prefix for the common
            # currencies, ISO-code suffix as fallback for anything else.
            if token_symbol == 'ETH':
                try:
                    currency = order.event.currency or 'USD'
                    symbol_map = {
                        'USD': '$', 'EUR': '€', 'GBP': '£',
                        'INR': '₹', 'JPY': '¥', 'CAD': 'C$', 'AUD': 'A$',
                    }
                    symbol = symbol_map.get(currency)
                    if symbol:
                        line += f' ({symbol}{payment.amount:.2f})'
                    else:
                        line += f' ({payment.amount:.2f} {currency})'
                except Exception:
                    pass
            lines.append(line)
        if chain_name:
            lines.append(f'Network: {chain_name}')
        if payer:
            lines.append(f'Payer: {payer}')
        if tx_url:
            lines.append(f'Transaction: {tx_url}')
        elif tx_hash:
            lines.append(f'Transaction: {tx_hash}')
        return '\n\n'.join(lines)

    def refund_control_render(self, request: HttpRequest, refund) -> str:
        """Render the refund details section on the Pretix order page. The
        refund's `info` JSON carries the on-chain tx hash + chain id we wrote
        in `record_pretix_refund`; surface them with an explorer link."""
        import json
        try:
            info = json.loads(refund.info or '{}') if isinstance(refund.info, str) else (refund.info_data or {})
        except (ValueError, TypeError):
            info = {}
        tx_hash = info.get('refund_tx_hash')
        chain_id = info.get('chain_id')
        explorer = CHAIN_METADATA.get(chain_id, {}).get('explorer_url', '')
        tpl = get_template('pretix_eth/refund.html')
        return tpl.render({
            'tx_hash': tx_hash,
            'chain_id': chain_id,
            'chain_name': CHAIN_METADATA.get(chain_id, {}).get('name'),
            'explorer_url': f'{explorer}{tx_hash}' if tx_hash and explorer else None,
        })

    def payment_refund_supported(self, payment):
        return False

    def payment_partial_refund_supported(self, payment):
        return False
