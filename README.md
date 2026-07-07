# Pretix Crypto Payment Plugin

A payment plugin for [Pretix](https://github.com/pretix/pretix) that accepts crypto payments and layers per-item crypto-vs-card pricing on top of Pretix's fiat (Stripe) checkout. Crypto is paid via direct WalletConnect checkout (user pays gas), verified directly on-chain — no vendor dependency. A gasless x402 flow (relayer pays gas for USDC/USDT0) also exists in the code but is **currently disabled** (see [Status](#status)).

## Status

- **Active crypto flow:** WalletConnect direct-send (`/plugin/wc/*`). This is the crypto path used in production.
- **Fiat (card) payments:** handled by Pretix's own Stripe plugin; this plugin adds per-item crypto-vs-card pricing, a card-price markup, and dual-currency display in the shop/cart (see [Fiat (card) payments](#fiat-card-payments)).
- **x402 gasless flow:** fully implemented but **disabled** — the x402 *buyer* routes (purchase, payment-options, relayer, verify, settings) are commented out in `pretix_eth/urls.py` (`_x402_routes()`), so those paths 404 and no x402 buyer-payment view runs. The code is retained; re-enable by uncommenting the routes. The x402 sections below document the flow as it works when re-enabled.
- **Admin/operator tools:** always registered under `/plugin/admin/*` (order dashboard, refunds, manual verify) — token- + permission-gated, and the order/stats views aggregate WalletConnect payments too, so the admin dashboard works regardless of the x402 gate. Renamed from the legacy `/plugin/x402/admin/*` misnomer.

## Supported chains & tokens

- **Chains:** Ethereum, Optimism, Polygon, Base, Arbitrum
- **Tokens:** USDC (all chains), USDT0 (Optimism, Arbitrum), native ETH (all chains)

## Payment flows

### WalletConnect (direct send)

User connects wallet, picks token+network, sends a standard ERC-20 `transfer` or native ETH send, plugin verifies on-chain.

1. Buyer selects "Crypto" at checkout and confirms the order
2. Pretix creates the order and redirects to the payment page
3. Buyer connects wallet via WalletConnect (MetaMask, Rainbow, Coinbase Wallet, etc.)
4. The picker fetches the wallet's per-(chain, token) balances via `/plugin/wc/wallet-balances/` (Zapper-first, RPC fallback — same engine the x402 flow uses) and displays them inline. Rows where the balance is below the order amount are tinted to flag clearly-empty wallets; the heuristic uses the live ETH price piggy-backed on `payment-options` so the picker check matches what the server enforces at quote time.
5. Buyer picks token and network, clicks "Pay now"
6. Plugin creates a quote (locked price, 10-min expiry) with a SIWE-lite signature challenge
7. Buyer signs the challenge (proves wallet ownership) then confirms the on-chain transfer
8. Plugin verifies the transaction on-chain via RPC
9. Order is marked as paid

### x402 gasless (USDC/USDT0)

Buyer signs an EIP-3009 `transferWithAuthorization`; a relayer broadcasts it and pays gas. No ETH needed in the buyer's wallet for stablecoin payments.

1. Frontend creates a purchase order via `/plugin/x402/purchase/` (pricing includes variations, addons, voucher discounts, crypto discount)
2. Frontend POSTs to `/plugin/x402/payment-options/` with the buyer's wallet — plugin returns a list of `PaymentOption[]` (per chain + token) with balances, sufficiency flags, and a pre-built `signingRequest` (EIP-712 typed data for USDC/USDT0, or `eth_sendTransaction` params for ETH)
3. Buyer picks an option and signs in their wallet (no gas for stablecoins)
4. For gasless stablecoins: frontend submits `{authorization, signature}` or `{authorization, rawSignature}` to `/plugin/x402/relayer/execute-transfer/`; plugin validates the authorization terms (recipient, amount, expiry) and broadcasts via relayer
5. Frontend polls `/plugin/x402/verify/` until on-chain confirmation
6. Plugin creates the Pretix order (with full variation / addon / answer / voucher parity) and marks it paid

### Native ETH (with payer signature)

Same as WalletConnect flow but with an additional `ethPayerSignature` at verify time that cryptographically binds the payer's wallet to the order. Supports:

- EOA (ECDSA recovery)
- Smart wallets (ERC-1271, with ERC-6492 unwrapping for counterfactual wallets)
- EIP-7702-delegated EOAs (e.g. MetaMask Smart Account in 7702 mode) — the verifier detects the `0xef0100…` code prefix and retries ERC-1271 against the wallet's chain-bound EIP-712 envelope (via `DOMAIN_SEPARATOR()`) when the plain EIP-191 hash is rejected
- ERC-4337 bundler flows — `debug_traceTransaction` walks internal calls to locate the actual ETH transfer when the outer `tx.from` is a bundler EOA

**Slippage tolerance:** ETH verification accepts up to **0.5%** under-payment vs. the quote (industry default, same as Uniswap). This absorbs two real-world drift sources without the merchant needing to over-quote:
- ETH spot price moves between when our oracles fetch it and when the wallet signs
- Smart-account wallets (notably MetaMask 7702 mode) re-derive `value` at signing time using their own price feed instead of passing the exact wei amount through

USDC/USDT0 transfers stay strict — stables don't drift, and the EIP-3009 typed-data signature commits to an exact value.

### Safe wallet support

- **Custom FE (devcon-next, x402 path):** supported, including multi-sig (e.g. 2/3). The FE bridges through Safe Transaction Service / Messages API to recover the on-chain hash for ETH and the assembled ERC-1271 signature for USDC/USDT0. Considered experimental; the buyer is shown a Safe-aware notice with a 30-min keep-tab-open window.
- **Pretix-native (wc_inject path):** Safe is **excluded** from the AppKit picker via `excludeWalletIds`. The bundle hasn't been ported yet and a Safe payer would land in a stuck state. Admin manual-verify (`/plugin/admin/verify/`) remains the recovery path for any Safe payment that bypasses the gate.

### Tx-hash recovery (broken WalletConnect sessions)

Some wallets broadcast a transaction successfully but fail to return the hash through the WalletConnect session — Binance Wallet on macOS is the canonical offender; Bitget Mobile and TokenPocket have shown the same bug intermittently. Without recovery the dapp's `sendTransactionAsync` promise never resolves and the buyer is stranded on "Confirm payment in wallet…" forever even though their funds already left.

Both the wc_inject bundle (`pretix_eth/static/wc_inject/src/components/CheckoutStep.tsx`) and the devcon-next x402 frontend wrap the wallet send in a recovery layer. Three paths race for the hash:

1. **Wallet → returns hash via WC/injected** (the happy path; ~always wins).
2. **Auto-discovery** — after a 20s grace, polls every 3s for a tx mined from the connected wallet at the broadcast nonce. Up to 60s total. wc_inject uses block-walking (no external API); the x402 FE uses Alchemy's `getAssetTransfers` (which already has Alchemy keys configured). Anchored to the chain head captured *before* the wallet send, so on fast chains (Base, Arbitrum) we don't miss txs that mined while the user was still confirming in their wallet.
3. **Manual hash entry** — if the auto window expires, an input surfaces so the buyer can paste the hash from their wallet's history. The pasted hash is validated on-chain (correct `from` and either `nonce`/`value` match) before the verify flow proceeds.

Console logs (`[wc_inject] tx-hash recovery: WALLET / DISCOVERY / MANUAL path won`) record which path resolved, so stuck-payment reports are diagnosable from a buyer's browser console alone.

## Fiat (card) payments

Card payments themselves are handled by Pretix's own Stripe plugin. This plugin adds a layer on top so the same ticket can be priced differently for crypto vs card, and so buyers see both prices before they choose.

Per-item behavior is driven by two `ItemMetaProperty` values (set per `Item` in the standard Pretix item editor, or bulk-applied):

- **`fiat_price_usd`** — the card price for this item. When set and higher than the item's `default_price` (the crypto price), card buyers pay the difference as a markup. Unset → card buyers pay `default_price`, no markup.
- **`fiat_disabled`** — set to `true` to hide Stripe entirely for any cart/order containing this item (crypto-only tickets). Add-ons follow their own metadata, not the parent's.

**How the card markup is applied.** The plugin monkey-patches Pretix's Stripe `calculate_fee` and order-placement path so the per-item delta `(fiat_price_usd − price)` is added:

- **New orders:** at placement the fiat price is baked directly into each `OrderPosition` (no separate fee line) when the buyer pays by card.
- **Change-payment-method / re-pay on an existing order:** the markup is resolved from the order's positions and added as a payment fee.
- The `calculate_fee` patch is installed only after the request-capture signals connect, so a Pretix signal rename can't leave it silently under-charging (it fails toward Stripe's native fee rather than a $0 markup).

**Buyer-facing display.** A small vanilla-JS bundle (`/plugin/wc/item-pricing.js`, injected on the catalog, cart, checkout, and voucher-redeem pages) annotates each item with both prices — a green "Ethereum" chip for the crypto price and a "Card" price beside it — reading per-event pricing from `/plugin/wc/item-pricing/`. On the cart it also relabels Pretix's generic "Payment fee" line to "Card payment fee" with a "difference between the ETH price and the card price" note. Display-only: invoices, emails, and the organizer backend keep Pretix's standard naming. Items where crypto and card prices match get no annotation.

**Chooser integration.** For crypto-only items (`fiat_disabled`), Stripe is hidden from the payment chooser and blocked on the order re-pay flow (`is_allowed`). For dual-priced items, the Stripe method label is prefixed with the live markup (e.g. "+$500 · Credit Card") so the buyer sees the card premium before committing.

## Pricing

- **Stablecoins:** 1 USDC = 1 USD (direct mapping)
- **ETH:** 4 oracles — Coinbase + **Binance.US** + Kraken + Bitstamp. Quorum logic: largest cluster of ≥2 prices agreeing within 5% wins; rest are dropped. Tolerates one or two oracles being unreachable.
- **POL:** 3 oracles — Coinbase + Binance.US + CoinGecko, same quorum.
- **Cache:** Successful quotes cached for 30s (Django cache backend). Failures aren't cached, so a transient outage retries immediately.
- **Vouchers:** Supported — set/subtract/percent price modes, per-item targeting.
- **Crypto discount:** Configurable percentage off, stacks with vouchers. Surfaces on the Pretix order as a negative `OrderFee(fee_type='payment')` row for both the WC-native and x402 paths.
- **Addon `price_included`:** Honored on the x402 path — addons whose parent ticket's `ItemAddOn.price_included=True` are charged $0 regardless of standalone price.

## Security

- **Authentication:** token-gated endpoints require a valid Pretix `TeamAPIToken` (`Authorization: Token <token>`) — the same token system Pretix uses for its own REST API, so there are no custom secrets to manage. Admin endpoints additionally require the team's `can_view_orders` / `can_change_orders` permission and check that the token's team belongs to the target event's organizer (cross-organizer access is rejected). **Known gap:** the organizer check does not yet honor per-team event scoping (`Team.limit_events`) — a token scoped to one event under an organizer can currently operate on other events under the same organizer. See Known gaps / TODOs.
- **USDC/USDT0 gasless:** Payer cryptographically bound via EIP-3009 signature (on-chain verified by token contract). Accepts both EOA (`{v, r, s}` object) and smart wallet (`rawSignature` hex) formats.
- **Native ETH:** Payer bound via `ethPayerSignature` — supports EOA (ECDSA), smart wallets (ERC-1271), counterfactual wallets (ERC-6492), and EIP-7702-delegated EOAs (chain-bound `DOMAIN_SEPARATOR()` retry). 0.5% slippage tolerance on the on-chain `value` to absorb price drift + wallet-side re-quoting (see Payment flows above)
- **Smart wallet ETH (ERC-4337):** `debug_traceTransaction` fallback walks internal call tree to find the actual ETH transfer from the smart wallet
- **WalletConnect direct:** SIWE-lite challenge at quote creation proves wallet ownership
- **Relayer binding:** Before sponsoring gas, the plugin verifies `authorization.to == configured recipient`, `authorization.value >= expected amount`, `authorization.from == intendedPayer`, and `validBefore > now` — an attacker with a valid token cannot redirect funds or underpay
- Transaction hash is single-use (prevents cross-order replay)
- Chain, token contract, sender, recipient, and amount all verified on-chain
- Rate limiting on the tokenless buyer-facing WalletConnect endpoints (challenge, create-quote, verify), keyed per-quote, per-`(order, challenge)`, and per-IP. Limits are env-tunable (see Environment overrides). Client IP is resolved from the trusted-proxy headers (`CF-Connecting-IP` / `X-Real-IP` / `X-Forwarded-For`) — this assumes the origin is network-locked to the CDN/proxy; if it isn't, those headers are client-spoofable and the per-IP caps can be bypassed (per-quote and per-order budgets still apply). Lock the origin to your proxy's IP ranges in production.
- Atomic claim + reserve prevents double-spend race conditions
- **Tx hash dedup is case-insensitive at read** (`tx_hash__iexact`) and lowercased at write — a mixed-case retry of an already-paid hash is rejected, and the unique-constraint race window between concurrent verifies can't be defeated by case twiddling
- **Admin manual verify** (`/plugin/admin/verify/`) intentionally bypasses the off-chain `ethPayerSignature` check for stuck-payment recovery — payer-binding falls back to the on-chain `tx.from == intended_payer` enforcement inside `verify_native_eth`. The endpoint is auth-gated by the Pretix API token and intended for operator-only use; the bypass is logged at WARNING for audit. Buyer-facing `/plugin/x402/verify/` keeps the signature requirement.
- **Cart-time race protection**: `Quota` rows and `Voucher` rows are locked with `SELECT ... FOR UPDATE` inside the order-creation transaction — concurrent x402 orders (and native-checkout orders, since both paths hit the same rows) can't oversell stock or exceed `Voucher.max_usages`. `require_voucher` is enforced server-side on tickets and addons; addons are also gated to categories actually allowed by a parent ticket so a buyer can't attach an arbitrary item via the API. Free-addon (`ItemAddOn.price_included`) pricing is capped per parent ticket's `max_count` so excess units are charged at full price instead of stacking.

## Setup

### 1. Install

```bash
pip install -e 'git+https://github.com/efdevcon/pretix-eth-payment-plugin.git@main#egg=pretix-eth-payment-plugin'
python -m pretix migrate pretix_eth
```

### 2. Configure

All settings are configurable via the Pretix admin UI (Settings > Payment). No environment variables required — env vars are optional overrides for production hardening.

| Setting | Required | Description |
|---|---|---|
| Receive address | Yes | EIP-55 wallet for the direct-send WalletConnect flow |
| Payment recipient | Yes | EIP-55 wallet for x402 gasless payments (usually same as Receive address) |
| WalletConnect project ID | Yes | Free from [cloud.reown.com](https://cloud.reown.com) |
| Alchemy API key | No | Improves RPC reliability; falls back to public RPCs |
| Zapper API key | No | When set, balance lookups (used by both the wc_inject picker and the x402 `payment-options` endpoint) go through Zapper's GraphQL API in a single round-trip (~200 ms) instead of fanning out RPC `eth_call`s per chain (~2 s). Falls back to RPC automatically if Zapper fails. Get a key at [zapper.xyz/api](https://zapper.xyz/api). |
| Relayer private key | No | Required for gasless USDC/USDT0 (fund the wallet with ETH on each supported chain for gas) |
| Crypto discount % | No | Percentage off fiat price for crypto payments (stacks on top of vouchers) |
| Chain toggles (×5) | No | Enable/disable individual chains (Ethereum, Optimism, Polygon, Base, Arbitrum) |
| Token toggles (×3) | No | Enable/disable individual tokens (USDC, USDT0, ETH) |
| Quote TTL | No | Default 600s (10 min) |
| Min confirmations | No | Default 1 |
| Support email | No | Buyer-facing "Need help?" mailto in the checkout UI; empty hides it |
| Frontend order URL template | No | Overrides the `{url}` placeholder in transactional emails. Use `{code}` and `{secret}` substitutions, e.g. `https://devcon.org/en/tickets/store/order/{code}/{secret}/` |

### 3. Environment overrides (optional)

| Variable | Purpose |
|---|---|
| `WC_ALCHEMY_API_KEY` | Overrides Alchemy key (preferred for production — not in DB) |
| `WC_RELAYER_PRIVATE_KEY` | Overrides relayer key (preferred for production — not in DB) |
| `WC_VERIFY_RATE_LIMIT_PER_MIN` | Verify attempts per `paymentReference` per minute (default 10) |
| `WC_VERIFY_IP_RATE_LIMIT_PER_MIN` | Verify attempts per IP per minute (default 120) |
| `WC_CREATE_QUOTE_IP_RATE_LIMIT_PER_MIN` | Create-quote attempts per IP per minute (default 20) |
| `WC_CREATE_QUOTE_PER_CHALLENGE_BUDGET` | Create-quote attempts per `(order, challenge)` (default 5) |
| `WC_BUYER_RATE_LIMIT_PER_MIN` | Per-IP cap on the other buyer endpoints (default 120) |

### 4. x402 proxy integration (devcon-next) — currently disabled

> **Note:** the x402 routes below are commented out in `pretix_eth/urls.py` and will 404 until re-enabled. This section describes the flow as it works once the routes are uncommented.

For the x402 gasless flow, devcon-next API routes proxy to the plugin using the existing Pretix API token (`PRETIX_API_TOKEN_DEV` / `PRETIX_API_TOKEN_PROD`). The plugin validates the token against Pretix's `TeamAPIToken` table via the `Authorization: Token <token>` header. No additional secrets needed.

Plugin endpoints (all accept JSON body with `organizer` + `event` slugs and camelCase field names):
- `POST /plugin/x402/purchase/` — create pending order (returns HTTP 402 + `{paymentDetails, orderSummary}`); supports tickets, variations, addons, answers, voucher
- `POST /plugin/x402/payment-options/` — given `{paymentReference, walletAddress}`, returns `PaymentOption[]` with balance, sufficiency, and pre-built `signingRequest` (EIP-712 for USDC/USDT0 or `eth_sendTransaction` for ETH)
- `POST /plugin/x402/relayer/prepare-authorization/` — returns EIP-712 typed data for a specific chain/token choice (alternative to payment-options for clients that don't want balances)
- `POST /plugin/x402/relayer/execute-transfer/` — relayer broadcasts the signed `transferWithAuthorization`; validates authorization terms against the pending order before spending gas
- `POST /plugin/x402/verify/` — verifies on-chain tx, creates Pretix order + `OrderPosition` rows (variations/addons/answers/voucher), confirms payment
Frontend field names: camelCase (`paymentReference`, `chainId`, `txHash`, `walletAddress`). The plugin's request body parser also accepts snake_case (`payment_reference`, `chain_id`, etc.) for non-frontend clients.

### Admin/operator endpoints (always on, `/plugin/admin/*`)

These are registered independently of the x402 buyer-flow gate — they're the operator tools behind the `/tickets/admin` dashboard, and `orders`/`stats` aggregate WalletConnect payments too. All require an admin token with the relevant permission (`can_view_orders` / `can_change_orders`) and are organizer-scoped.

- `GET /plugin/admin/orders/` — list completed + pending orders (WC + x402)
- `GET /plugin/admin/stats/` — dashboard aggregates (counts, total_usd via DB aggregate)
- `POST /plugin/admin/refund/?action=initiate|confirm|fail` — x402 refund state machine
- `POST /plugin/admin/verify/` — manually confirm a stuck x402 payment (bypasses the off-chain ETH signature; still runs on-chain verification)
- `POST /plugin/admin/wc-refund/?action=initiate|confirm|fail` — refund a WalletConnect payment
- `POST /plugin/admin/wc-verify/` — manually confirm a stuck WalletConnect payment; requires the order secret and still runs full on-chain verification (can't fake a payment)

> Renamed from the legacy `/plugin/x402/admin/*` prefix (these are shared crypto-admin tools, not x402-only). The devcon-next proxies at `/api/x402/admin/*` were updated to target the new paths; their own frontend-facing URLs are unchanged.

## Known gaps / TODOs

These are documented, non-blocking items for a future iteration:

- **Event-level authorization scoping**: admin endpoints now enforce a valid token, the required permission flag (`can_view_orders` / `can_change_orders`), AND that the token's team belongs to the target event's **organizer** (`check_team_event_access` in `x402/auth.py`, cross-organizer rejected). What remains: the check is organizer-level only and ignores per-team event scoping (`Team.limit_events`), so a token scoped to one event can still act on sibling events under the same organizer. Fix: have `check_team_event_access` consult `team.all_events` / `team.limit_events` (or reuse Pretix's `team.permission_for_event`). Also note `check_team_event_access` returns `True` when no team is set (a fail-open primitive currently unreachable because the decorator rejects a missing token first — worth flipping to fail-closed defensively).
- **Order-redirect over `http://`**: the post-payment redirect (`/plugin/wc/order-redirect.js`, driven by the "Frontend order URL template" setting) accepts `http://` templates. The redirect URL carries the order secret in its path, so an `http://` template transmits that secret in cleartext (MITM order-takeover risk). The template is admin-only input (not attacker-controllable), so this is operator-footgun rather than an open redirect — but `http://` should be restricted to loopback hosts. Also note the order secret currently rides in a `?secret=` query param on the injected `<script src>`, which can land in web-server access logs.
- **Agent endpoint** (`/purchase/[email].ts` in devcon-next): currently stubbed at HTTP 501. If x402 SDK agents need to work, add a `/plugin/x402/purchase-agent/` endpoint that skips the `intendedPayer` requirement.
- **Verify cooldown**: the 10-second-between-attempts cooldown from devcon's ticketStore was removed during Phase 3 (conflicted with a test that didn't mock time). The 10/hour and 30/minute limits still apply — add the cooldown back with time-mocked tests if spam protection needs tightening.
- **Direct browser → plugin calls**: the public endpoints (`purchase`, `payment-options`, `relayer/*`, `verify`) currently require a server-side Pretix API token. If we want to skip the devcon-next proxy entirely and have the browser call the plugin directly, we'd need to drop the `Authorization: Token` requirement on those specific endpoints and add CORS.
- **Admin-initiated refunds for legacy rows**: the on-chain refund button in the devcon admin UI is gated to `source === 'x402'` because the refund CAS state machine (`refund_status`/`refund_tx_hash`/`refund_meta`, locked via `SELECT FOR UPDATE` on `payment_reference`) only exists on `X402CompletedOrder`. `WCPaymentAttempt` and `SignedMessage` have no refund columns, so double-refund protection is missing. Fix: introduce a unified `ManualCryptoRefund` model keyed `(source, row_id)` with a unique constraint; refund UI branches request path by `source` with no schema change to legacy tables.
- **Relayer balance monitoring** (from the gas-condition rework): `assert_gas_conditions` no longer blocks a tx when the relayer wallet is low; a drained relayer now surfaces only as a customer-facing 502. Add an admin-UI balance dashboard or periodic probe so operators see low balances out-of-band. Marked as a TODO in `x402/gas.py`.
- **Native Pretix-checkout UI upgrade to x402 parity**: the `WalletConnectPayment` provider (`payment.py` + `checkout_payment_confirm.html` + `static/wc_inject/dist/bundle.js`) still uses the legacy `/plugin/wc/*` direct-send flow (user pays gas, writes to `WCPaymentAttempt`). Port it to the x402 stack so Pretix-native checkout gets balance fetch, multi-chain/token picker, gasless EIP-3009, and writes to `X402CompletedOrder`. Sketch: add a native-purchase endpoint that takes an existing `order_code` (instead of creating one on verify), a same-origin auth bridge so the browser can call `/plugin/x402/*` without a TeamAPIToken, and port the pay-column logic from `devcon/src/pages/tickets/store/checkout.tsx`. Estimated ~1 to 1.5 weeks (~3 days for a stripped single-chain variant).
- **Per-item crypto-payment disable**: allow admins to mark specific items (tickets or add-ons) as ineligible for crypto payment. Scope: (1) one plugin setting — a `ModelMultipleChoiceField` scoped to `Item.objects.filter(event=event)`, stored via hierarkey; (2) enforce in `/plugin/x402/purchase/` (reject 400 if any `tickets[]` or `addons[]` item is blocked — reject the whole cart, no per-line-item split); (3) `payment.py.is_allowed(request, total, order)` returns False when an order contains a blocked position so Pretix-native checkout automatically hides the method; (4) expose the blocklist in `/api/x402/tickets/` so the devcon store greys out the crypto button on blocked rows; (5) tests for blocked-only cart, mixed cart, allowed cart, native-checkout hiding. Decisions baked in: cart-level rejection (not split), item-level (not variation-level), voucher-agnostic. Estimated ~2-3h.
- **Bump-and-rebroadcast for a stuck relayer tx**: when the relayer's `transferWithAuthorization` is underpriced for current network conditions, the tx sits in mempool and eventually drops. Buyer sees "verifying…" until the frontend's 90 s budget exhausts; the authorization is unconsumed (not a financial loss — funds never left the buyer's wallet — but a UX loss). The 25 % `maxFeePerGas` headroom in `relayer.py` covers most spikes; this TODO is for the long tail. Scope: (1) on broadcast, persist `(tx_hash, nonce, chain_id, broadcast_at)` next to the `X402PendingOrder` so we can recover the relayer state; (2) periodic task every ~15 s checks each unsettled relayer tx — if `eth_getTransactionByHash` returns `None` (dropped) AND the nonce is still next-up on the relayer account, rebuild with `maxFeePerGas × 1.5` and re-broadcast; if `eth_getTransactionReceipt` exists, mark settled and let normal verify finalize; (3) cap retries at 3 to bound merchant gas spend per stuck order; (4) on final-give-up, mark the pending order with a `relayer_failed` flag so the buyer sees a clear "please retry — your funds were not charged" message and can re-initiate. Estimated ~120 lines, ~2-3 h focused work. Buyer's authorization `validBefore` (default 10 min) caps the rescue window naturally.
- **Reorg monitoring (optimistic-accept, deferred-verify)**: when `min_confirmations` is set to 0 the buyer flow is fastest, but a 1-block reorg on Ethereum L1 (~0.05–0.1% of slots) or Polygon (a few small reorgs/day) could orphan a tx we accepted. Build a deferred-finality sweep so we get the UX of 0-confs and the safety of multi-conf. Scope: (1) add `reorg_check_state` ('pending'|'safe'|'reorged'), `reorg_checked_at`, `recorded_block_hash` columns to `X402CompletedOrder` (one migration); (2) capture `block_hash` at verify time alongside `block_number`; (3) periodic task (~60s cadence, register via the existing `periodic_task` signal) re-fetches the receipt for any `reorg_check_state='pending'` row past a per-chain delay (L2 rollups: 30s/1 conf, Ethereum L1: 180s/12 confs, Polygon: 60s/16 confs); (4) on intact `block_hash` + sufficient depth → mark `safe`; on differing `block_hash` → benign re-mine, update hash and stay pending one more cycle; on missing receipt → mark `reorged`, call `_cancel_order(send_mail=True)`, log WARNING; (5) admin UI badge on the completed table (`⏳ verifying` while pending, `🚩 reorged — order canceled` on reorged rows) plus a filter chip; (6) require 2 consecutive RPC failures before declaring `reorged` (defensive against flaky providers); (7) tests covering happy path / re-mine / orphaned. Prereq: do this *before* lowering the global `min_confirmations` from 1 to 0. Estimated ~200–250 lines, ~2-3h focused work. Decisions baked in: auto-cancel (not flag-only), no on-chain refund (a reorged tx by definition didn't pay us — the buyer's funds never left their wallet).
- **Migrate order creation to Pretix's native `OrderCreator`**: today `pretix_eth/x402/pretix_client.py:create_pretix_order` instantiates `OrderPosition` rows directly and reimplements quota lock, voucher race protection, `require_voucher`, addon category gate, free-addon `max_count`, and `price_included` semantics. Pretix's `pretix.base.services.orders._perform_order` does all of this. Scope: at purchase time build `CartPosition` rows (extending `cart_expiry` to match the 1-hour payment window); at verify time call `_perform_order` with the cart + the `walletconnect` payment provider; delete the manual checks; keep a thin x402-side guard so `total=0` carts don't reach the on-chain verifier. Trade-off: ties the plugin to a private Pretix API (`_perform_order`), so pin a Pretix version range and re-test on upgrade. Estimated 1–2 days + voucher/addon/quota regression suite.
- **Admin manual verification for legacy Pretix-native checkout (wc_inject)**: buyer self-serve recovery (manual hash paste, see "Tx-hash recovery" above) now covers the common case of "wallet broadcast but never returned the hash via WC". The remaining stuck-payment cases (browser tab closed before pasting, network failure during verify, etc.) still require admin reconciliation in Pretix's backend. Build a narrow admin endpoint that covers the common case: *the user made it through the bundle's step 3 (quote creation) and broadcast the tx, but something failed before confirm*. Scope: (1) show wc_inject pendings in the devcon admin pending table (query `OrderPayment.objects.filter(order__event=event, provider='walletconnect', state='created')` alongside `X402PendingOrder`, with a `source: 'wc_inject'` discriminator); (2) `admin_verify_wc_inject` endpoint keyed on `order_code` that reads `OrderPayment.info_data['quote']` and refuses if absent (out of scope — direct to Pretix native admin); (3) **explicitly ignore the quote TTL** in this endpoint — the tx's `amount_raw` was locked at quote time, the user already paid that amount, so TTL-based price-drift checks don't apply; the admin is accepting any economic drift as part of the recovery; (4) re-run `verify_native_eth` / `verify_erc20_transfer` against the quote's `amount_raw` + `intended_payer` + `receive_address`, then `WCPaymentAttempt.objects.create(...)` atomically + `payment.confirm()`. No new ETH signature input needed — the challenge signature was already verified at quote-creation. Estimated ~2-3h, and will become dead code once the native-UI upgrade above lands, so worth deferring unless wc_inject stuck-payment volume is actually a pain.

## Development

Requires Python 3.10+ and Node 20+.

```bash
git clone https://github.com/efdevcon/pretix-eth-payment-plugin.git
cd pretix-eth-payment-plugin
pip install -e '.[dev]'

# Build frontend (WalletConnect checkout UI)
cd pretix_eth/static/wc_inject
pnpm install
pnpm run build   # or: pnpm run watch

# Run tests
cd ../../..
pytest tests/ -v
```

## History

It started with [ligi](https://github.com/ligi) suggesting [pretix for Ethereum
Magicians](https://ethereum-magicians.org/t/charging-for-tickets-participant-numbers-event-ticketing-for-council-of-paris-2019/2321/2).

Then it was used for Ethereum Magicians in Paris (shout out to
[boris](https://github.com/bmann) for making this possible) - but accepting ETH
or DAI was a fully manual process there.

Afterwards boris [put up some funds for a gitcoin
bounty](https://github.com/spadebuilders/community/issues/30) to make a plugin
that automates this process. And [nanexcool](https://github.com/nanexcool)
increased the funds and added the requirement for DAI.

The initial version was developed by [vic-en](https://github.com/vic-en) but he
vanished from the project after cashing in the bounty money and left the plugin
in a non-working state.

Then the idea came up to use this plugin for DevCon5 and the plugin was forked
to this repo and [david sanders](https://github.com/davesque), [piper
merriam](https://github.com/pipermerriam), [rami](https://github.com/raphaelm),
[Pedro Gomes](https://github.com/pedrouid), and [Jamie
Pitts](https://github.com/jpitts) brought it to a state where it is usable for
DevCon5 (still a lot of work to be done to make this a good plugin). Currently,
it is semi-automatic. But it now has ERC-681 and Web3Modal
support. If you want to dig a bit into the problems that emerged short before
the launch you can have a look at [this
issue](https://github.com/esPass/pretix-eth-payment-plugin/pull/49)

For DEVcon6 the plugin was extended with some more features like [Layer2 support by Rahul](https://github.com/rahul-kothari). Layer2 will play a significant [role in Ethereum](https://ethereum-magicians.org/t/a-rollup-centric-ethereum-roadmap/4698). Unfortunately DEVcon6 was delayed due to covid - but we where able to use and this way test via the [LisCon](https://liscon.org) ticket sale. As far as we know this was the first event ever offering a Layer2 payment option.
In the process tooling like [Web3Modal](https://github.com/Web3Modal/web3modal/) / [Checkout](https://github.com/Web3Modal/web3modal-checkout) that we depend on was improved.

For Devconnect IST an effort was made to improve the plugin in a variety of ways: WalletConnect support, single receiver mode (accept payments using just one wallet), more networks, automatic ETH rate fetching, improved UI and messaging, and smart contract wallet support. All of these features made it into this version of the plugin, except for smart contract wallet support - issues processing transactions stemming from sc wallets meant that we ultimately had to turn away sc wallet payments altogether.

For Devconnect 2025, the plugin was rewritten to use [Daimo Pay](https://pay.daimo.com), providing any-chain checkout and automatic refunds. See [DIP-64](https://forum.devcon.org/t/dip-64-universal-checkout-for-devcon-nect/5346).

For Devcon 8, the plugin was rebuilt from scratch by [Didier Krux](https://github.com/didierkrux) with two payment modes: direct WalletConnect checkout (user pays gas) and x402 gasless (relayer pays gas for stablecoins). All crypto logic now lives natively in the Pretix plugin — no external database (Supabase retired), no vendor dependency (Daimo Pay removed). Smart wallet support (ERC-1271, ERC-6492, ERC-4337) was added for both payment paths. The devcon-next frontend proxies to the plugin via Pretix API tokens.

Ahead of the Devcon 8 launch the scope was narrowed to WalletConnect direct-send as the sole crypto path, with the x402 gasless flow disabled (routes commented out, code retained) pending a security review. In parallel, a fiat layer was added on top of Pretix's Stripe plugin: per-item crypto-vs-card pricing (`fiat_price_usd` / `fiat_disabled` item metadata), a card-price markup applied as a payment fee, dual-currency price display across the shop/cart/voucher-redeem pages, and Safe (multisig) support for the WalletConnect flow.
