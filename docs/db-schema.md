# `pretix_eth` — DB schema

Five tables. Two flows (legacy WC + x402) plus one shared rate-limit ledger
and one legacy artifact kept for migration compatibility.

## Tables

### `pretix_eth_signedmessage` (LEGACY)

Pre-WC EIP-712 / Safe-Tx flow. Kept around so the historical migrations
graph still resolves — current code paths don't write here. Don't touch
unless restoring an old order.

```
id                       BIGINT PK (auto)
signature                VARCHAR(132)        -- 0x + 130 hex
raw_message              TEXT
sender_address           VARCHAR(42)         -- 0x + 40 hex
recipient_address        VARCHAR(42)
chain_id                 INT
order_payment_id         FK → OrderPayment   (CASCADE; related_name=signed_messages)
transaction_hash         VARCHAR(66) UNIQUE NULL
safe_app_transaction_url TEXT UNIQUE NULL
invalid                  BOOL DEFAULT false
created_at               DATETIME NULL       (auto-set in save())
is_confirmed             BOOL DEFAULT false
```

### `pretix_eth_wcpaymentattempt` — WC flow

One row per accepted on-chain payment for the legacy WalletConnect (direct
Transfer) flow. The `tx_hash` UNIQUE constraint is the
one-time-use guarantee — the V45 fix canonicalises hex case
(see migration `0014`) so this constraint actually catches case-different
duplicates that would have slipped pre-fix.

```
id          BIGINT PK (auto)
tx_hash     VARCHAR(66) UNIQUE INDEX        -- lowercase 0x + 64 hex (post-V45)
quote_id    VARCHAR(32) INDEX
order_code  VARCHAR(16)                     -- Pretix order code
payer       VARCHAR(42)
chain_id    INT
state       VARCHAR(16)                     -- 'claiming' | 'completed'
created_at  DATETIME (auto_now_add)
```

State machine: `claiming` → `completed`. `claiming` is the in-flight slot
during the atomic verify+confirm; `completed` rows are the canonical
"this tx settled this order" records. The dedup pre-check + the unique
constraint together prevent the V45 case-race.

### `pretix_eth_x402pendingorder` — x402 pre-payment scratch

Pending x402 ticket purchase between the storefront's `/purchase/` call
and the buyer's payment confirmation. Garbage-collected after
`expires_at`. Never references a Pretix `Order` (those don't exist yet —
they're created at verify time).

```
payment_reference                VARCHAR(100) PK            -- server-generated, single-use
event_id                         FK → pretixbase.Event (CASCADE; related_name=x402_pending_orders)
order_data                       JSON                       -- cart snapshot (items, voucher, attendee, …)
total_usd                        DECIMAL(12,2)
created_at                       DATETIME (auto_now_add)
expires_at                       DATETIME INDEX             -- TTL — 1h after creation
intended_payer                   VARCHAR(42)
expected_eth_amount_wei_by_chain JSON NULL                  -- {chain_id: wei} for ETH symbol
expected_chain_id                INT NULL
metadata                         JSON NULL                  -- discount info, optional flags

INDEX (event_id, expires_at)
```

### `pretix_eth_x402completedorder` — x402 settled

Mirrors `WCPaymentAttempt` but for the x402 flow. Adds USD/crypto totals,
gas accounting, and refund tracking — x402 admin views render directly
from this table rather than from Pretix's `OrderPayment.info_data`.

```
payment_reference VARCHAR(100) PK            -- carries through from PendingOrder
event_id          FK → pretixbase.Event (CASCADE; related_name=x402_completed_orders)
tx_hash           VARCHAR(66) UNIQUE INDEX   -- lowercase post-V45 (see 0014)
pretix_order_code VARCHAR(16) INDEX          -- the Pretix order this settled
payer             VARCHAR(42)
completed_at      DATETIME (auto_now_add)
chain_id          INT
total_usd         DECIMAL(12,2)
token_symbol      VARCHAR(20)                -- 'USDC', 'USDT', 'ETH', …
crypto_amount     VARCHAR(50) NULL           -- string-of-int (raw token units)
gas_cost_wei      VARCHAR(50) NULL
refund_status     VARCHAR(16) NULL INDEX     -- 'pending' | 'confirmed' | 'failed'
refund_tx_hash    VARCHAR(66) NULL
refund_meta       JSON DEFAULT {}            -- refund admin context

INDEX (event_id, completed_at DESC)
INDEX (event_id, refund_status)
```

### `pretix_eth_x402verifyattempt` — rate-limit ledger

Used by the rate-limiter helpers to count attempts in a sliding window.
A row is `INSERT`ed on every throttled request; the limiter `COUNT(*)`s
the rows for `key` in the last N seconds.

```
id          BIGINT PK (auto)
key         VARCHAR(120) INDEX        -- e.g. 'verify_ref:<ref>', 'verify_ip:<ip>',
                                      --      'purchase_ip:<ip>', 'wc_verify_ip:<org>:<event>:<ip>'
created_at  DATETIME INDEX (auto_now_add)
```

A periodic vacuum (drop rows older than the largest window) keeps the
table bounded — without one, this grows linearly with traffic.

## Cross-flow invariants

- **`tx_hash` lowercased** on both `WCPaymentAttempt` and
  `X402CompletedOrder` post-V45 (migration `0014`). New writes from
  `views.py:verify` and `views_x402.py:verify` lowercase before insert.
- **`payment_reference` is the spine of the x402 flow** — same value on
  the `X402PendingOrder` row and the matching `X402CompletedOrder` row.
- **No FK between WC-side `WCPaymentAttempt` and `Order`** — joined by
  `order_code` (string) at query time.
- **No FK between x402-side `X402CompletedOrder` and `Order`** — joined by
  `pretix_order_code` (string) at query time.

## Migration history (relevant subset)

```
0010 — WCPaymentAttempt added              (legacy WC flow goes live)
0011 — X402PendingOrder added              (x402 flow scaffolded)
0012 — X402CompletedOrder added            (x402 settles into its own table)
0013 — X402VerifyAttempt added             (rate-limit ledger)
0014 — lowercase tx_hash backfill          (V45 fix; dedup pre-step for dirty DBs)
```

## Things this schema deliberately doesn't do

- **No FK between completion rows and Pretix `Order`.** The Pretix order
  is created via `Order.objects.create()` at settle time; the completion
  row carries the order code as a string so the plugin can be uninstalled
  without leaving dangling FKs.
- **No history table for state transitions.** `state` on
  `WCPaymentAttempt` is just current-state; the migration trail + Django's
  `created_at` are the only audit signal.
- **No retention policy** on `X402VerifyAttempt`. Operate a
  cron/management-command vacuum if traffic warrants it.
