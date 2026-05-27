import { useState, useEffect, useRef, useCallback } from 'react'
import {
  useAccount,
  useSignMessage,
  useSwitchChain,
  useWriteContract,
  useSendTransaction,
  useConfig,
} from 'wagmi'
import { useWalletInfo } from '@reown/appkit/react'
import { classifyConnection, connectionTypeLabel, walletLocationPhrase } from '../walletConnection'
import {
  waitForTransactionReceipt,
  getTransaction,
  getTransactionCount,
  getBlock,
  getBlockNumber,
  sendCalls,
  getConnectorClient,
} from 'wagmi/actions'
import { erc20Abi, encodeFunctionData } from 'viem'
import {
  getCapabilities as viemGetCapabilities,
  waitForCallsStatus as viemWaitForCallsStatus,
  signMessage as viemSignMessage,
} from 'viem/actions'
import { NETWORK_LOGOS, TOKEN_LOGOS } from '../assetIcons'
import type { WCConfig } from '../config'
import type { PaymentOption } from '../hooks/usePaymentOptions'
import type { Quote } from '../WCPaymentApp'
import { useWalletBalances, findBalance, formatBalance } from '../hooks/useWalletBalances'
import { WalletHeader } from './WalletHeader'
import {
  isSafeWallet,
  probeSafe,
  pollSafeTxService,
  pollSafeMessagesService,
  looksLikeSafeMessageHash,
} from '../utils/safe'

// Per-chain block time (ms). The verify-poll interval is derived from this
// so we don't waste polls on slow chains (Ethereum L1 ~12 s blocks) and
// don't burn the API on fast chains (Arbitrum ~250 ms blocks).
const BLOCK_TIME_MS: Record<number, number> = {
  1: 12_000,    // Ethereum
  10: 2_000,    // Optimism
  137: 2_000,   // Polygon
  8453: 2_000,  // Base
  42161: 250,   // Arbitrum
}

/** Poll at 2 s on Ethereum L1 (so we don't sit idle for ~6 s after the
 *  block lands while waiting on receipt indexing) and 1.5 s on faster
 *  chains. Cap at 2 s upper bound — RPC indexer lag is the real latency
 *  source on L1, not block time itself, so polling more often than once
 *  per block actually pays off. */
function pollIntervalMs(chainId: number): number {
  const blockTime = BLOCK_TIME_MS[chainId] ?? 4_000
  return Math.max(1_500, Math.min(2_000, Math.floor(blockTime / 2)))
}

/** Total poll budget = enough to wait for the confirmation requirement
 *  plus one extra block of slack. Bounded at 90 s so a stuck chain
 *  surfaces as an error rather than hanging forever. */
function pollMaxDurationMs(chainId: number, requiredConfs: number): number {
  const blockTime = BLOCK_TIME_MS[chainId] ?? 4_000
  return Math.min(90_000, blockTime * (requiredConfs + 1) + 4_000)
}

// Centralized debug logger. All wc_inject runtime logs share the same
// `[wc_inject]` prefix so they can be grepped/filtered in a buyer's
// browser console when triaging a stuck payment. Use `dbg` for happy-path
// milestones (info level), `warn` for caught/expected failures (capability
// probe missing, switchChain rejected, etc.), and `err` for the
// hard-fail catch in handlePay.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function dbg(event: string, fields?: Record<string, any>) {
  // eslint-disable-next-line no-console
  console.info(`[wc_inject] ${event}`, fields ?? {})
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function dbgWarn(event: string, fields?: Record<string, any>) {
  // eslint-disable-next-line no-console
  console.warn(`[wc_inject] ${event}`, fields ?? {})
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function dbgErr(event: string, fields?: Record<string, any>) {
  // eslint-disable-next-line no-console
  console.error(`[wc_inject] ${event}`, fields ?? {})
}

// Backend verify errors that are transient (RPC indexer lag after tx is mined,
// trace endpoint briefly unavailable, etc.) and should auto-retry instead of
// bailing. `not found` covers the common `get_transaction_receipt` case where
// the user's wallet RPC has seen the tx but the backend RPC hasn't yet indexed it.
const RETRYABLE_ERROR_SUBSTRINGS = [
  'tx not mined yet',
  'insufficient confirmations',
  'not found',
  'rpc error',
]

const SYMBOL_DISPLAY: Record<string, string> = { USDT0: 'USD₮0' }

function displaySymbol(sym: string): string {
  return SYMBOL_DISPLAY[sym] ?? sym
}

/** Format a list of token symbols as English-readable copy
 *  ("USDC or USDT0", "USDC, USDT0, or DAI", etc.). */
function englishList(items: string[]): string {
  const xs = items.map(displaySymbol)
  if (xs.length === 0) return ''
  if (xs.length === 1) return xs[0]
  if (xs.length === 2) return `${xs[0]} or ${xs[1]}`
  return `${xs.slice(0, -1).join(', ')}, or ${xs[xs.length - 1]}`
}

/** Reason copy is built dynamically from the fallback symbols actually
 *  enabled in this event's plugin config — never hard-codes "USDC or USDT0"
 *  if either is disabled. Falls back to a generic phrase if no stable is
 *  enabled (an event configured ETH-only would just stay broken at the
 *  picker anyway, but the message stays correct). */
function ethReasonText(reason: string, fallbackSymbols: string[]): string {
  const fallback = fallbackSymbols.length
    ? `Please pay with ${englishList(fallbackSymbols)} instead.`
    : 'Please try again later.'
  if (reason === 'oracle_unavailable_or_diverged') {
    return `ETH payments temporarily unavailable. Our price oracles (Coinbase, Binance) disagree by more than 5% or are unreachable. ${fallback}`
  }
  if (reason === 'oracle_error') {
    return `ETH payments temporarily unavailable due to a price lookup error. ${fallback}`
  }
  return `ETH payments temporarily unavailable. ${fallback}`
}

type Status =
  | 'idle'
  | 'challenge'
  | 'signing-challenge'
  | 'quoting'
  | 'switching'
  | 'signing-tx'
  | 'verifying'
  | 'success'
  | 'error'

/** Format a raw onchain integer (wei for ETH, base units for stables) at
 *  full precision via BigInt division. The previous `Number(BigInt(...)) / 1e18`
 *  + `.toFixed(6)` path lost both arithmetic precision (Number caps at ~15 sig
 *  figs) and display precision — small ETH amounts like 4_333_520_758_106 wei
 *  rendered as "0.000004 ETH" instead of "0.000004333520758106 ETH", hiding
 *  the actual amount the buyer was about to authorize. We now show every
 *  significant digit; the wallet's confirm popup will show the same number,
 *  so they should match exactly. */
function formatRawAmount(rawStr: string, decimals: number): string {
  try {
    const n = BigInt(rawStr)
    const ZERO = BigInt(0)
    if (n === ZERO) return '0'
    const base = BigInt('1' + '0'.repeat(decimals))
    const whole = n / base
    const frac = n % base
    if (frac === ZERO) return whole.toString()
    const fracStr = frac.toString().padStart(decimals, '0').replace(/0+$/, '')
    return `${whole}.${fracStr}`
  } catch {
    return rawStr
  }
}

function formatAmount(q: Quote): string {
  const decimals = q.symbol === 'ETH' ? 18 : 6
  return `${formatRawAmount(q.amount_raw, decimals)} ${q.symbol}`
}

/** Robust receipt-waiter that handles wallet-side speed-ups and cancellations
 *  even when our chain RPC didn't see the original tx broadcast.
 *
 *  Strategy: race two paths against each other.
 *   (a) viem's `waitForTransactionReceipt(hash, onReplaced)` — succeeds
 *       quickly in the happy path, also detects replacement IF our RPC has
 *       the original tx's from/nonce cached.
 *   (b) Nonce-based fallback — captures the broadcast nonce, polls
 *       `getTransactionCount(payer, 'latest')`, and once it advances we walk
 *       recent blocks looking for any tx whose `from === payer && nonce ===
 *       broadcastNonce`. Resolves with the hash of *whatever* mined at that
 *       nonce — original, sped-up replacement, or even a wallet-side cancel
 *       (a 0-value self-tx, which the backend then rejects with "no
 *       matching transfer", surfacing the right error to the user).
 *
 *  Returns `{ hash, cancelled }`. `cancelled=true` means viem fired
 *  `onReplaced({reason:'cancelled'})` — caller should treat as user abort.
 */
async function waitForReceiptOrReplacement(opts: {
  wagmiConfig: Parameters<typeof waitForTransactionReceipt>[0]
  chainId: number
  hash: `0x${string}`
  payer: `0x${string}`
  /** The nonce captured BEFORE broadcast (= getTransactionCount(payer, 'pending')
   *  at the moment just before the wallet was asked to sign). Authoritative —
   *  use this when available so we don't have to guess. */
  expectedNonce?: number
}): Promise<{ hash: `0x${string}`; cancelled: boolean }> {
  const { wagmiConfig, chainId, hash, payer } = opts

  // Caller passes `expectedNonce` (captured BEFORE broadcast) — that's the
  // unambiguous identifier for this payment regardless of how many times
  // it gets replaced. Falling back to fetching from the tx itself, and
  // finally to `pending` if nothing else works (last-ditch — race-prone).
  let broadcastNonce = opts.expectedNonce ?? null
  if (broadcastNonce == null) {
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const tx = await getTransaction(wagmiConfig, { hash, chainId })
        if (tx?.nonce != null) {
          broadcastNonce = Number(tx.nonce)
          break
        }
      } catch {
        // not seen yet
      }
      await new Promise(r => setTimeout(r, 700))
    }
  }
  if (broadcastNonce == null) {
    try {
      const pending = await getTransactionCount(wagmiConfig, {
        address: payer, blockTag: 'pending', chainId,
      })
      broadcastNonce = Math.max(0, pending - 1)
    } catch {
      broadcastNonce = -1
    }
  }

  let cancelled = false

  const viemPath = waitForTransactionReceipt(wagmiConfig, {
    hash,
    chainId,
    onReplaced(replacement: { reason: string }) {
      if (replacement.reason === 'cancelled') cancelled = true
    },
  }).then(receipt => receipt.transactionHash as `0x${string}`)

  const noncePath = (async (): Promise<`0x${string}`> => {
    if (broadcastNonce === -1) {
      // Sit forever — viem's path is the only chance.
      return new Promise<`0x${string}`>(() => {})
    }
    const startBlock = await getBlockNumber(wagmiConfig, { chainId }).catch(() => null)
    let walkFrom = startBlock != null ? startBlock - 5n : null
    while (true) {
      await new Promise(r => setTimeout(r, 3000))
      let latestNonce: number
      try {
        latestNonce = await getTransactionCount(wagmiConfig, {
          address: payer, blockTag: 'latest', chainId,
        })
      } catch {
        continue
      }
      if (latestNonce <= broadcastNonce) continue

      // Nonce has advanced past our broadcast — find the hash by walking
      // blocks from a few before broadcast up to current head.
      const head = await getBlockNumber(wagmiConfig, { chainId }).catch(() => null)
      if (head == null) continue
      const fromBlock = walkFrom ?? head - 25n
      walkFrom = head + 1n
      for (let bn = fromBlock; bn <= head; bn++) {
        let txs: Array<{ from: string; nonce: number; hash: string }> = []
        try {
          const block = await getBlock(wagmiConfig, {
            blockNumber: bn, includeTransactions: true, chainId,
          })
          // With `includeTransactions: true` viem returns full Transaction
          // objects; the type union just confuses TS without the runtime
          // discriminator, so we narrow defensively.
          txs = (block?.transactions as Array<{ from: string; nonce: number; hash: string }>) ?? []
        } catch {
          continue
        }
        const match = txs.find(
          t => t?.from?.toLowerCase() === payer.toLowerCase() && Number(t?.nonce) === broadcastNonce
        )
        if (match?.hash) return match.hash as `0x${string}`
      }
    }
  })()

  const winner = await Promise.race([viemPath, noncePath])
  return { hash: winner, cancelled }
}

/**
 * Standalone nonce-discovery: walks blocks looking for any tx mined from
 * `payer` at `expectedNonce`. Used as a tx-hash recovery path for wallets
 * that broadcast successfully but fail to return the hash via WC (Binance
 * Wallet macOS being the canonical example). Since we capture the nonce
 * BEFORE asking the wallet to sign, any matching mined tx is unambiguously
 * the tx the user just authorized — works for both ETH and ERC20 transfers
 * (same payer, same nonce, regardless of contract data).
 *
 * Loops forever until cancelled via `signal.aborted`. Caller is responsible
 * for racing this against the wallet promise + a timeout.
 */
async function discoverTxByNonce(opts: {
  wagmiConfig: Parameters<typeof waitForTransactionReceipt>[0]
  chainId: number
  payer: `0x${string}`
  expectedNonce: number
  signal: { aborted: boolean }
  /** Block number captured immediately BEFORE the wallet was asked to sign.
   *  Used as the lower bound for the block walk so we don't miss txs that
   *  mined while the user was still confirming in their wallet. Without this
   *  we'd anchor to discovery-start instead, which on fast chains (Base,
   *  Arbitrum) can already be 15–25 blocks past the broadcast — far enough
   *  that a `head - 5` lookback never finds the tx. */
  preSendBlock?: bigint
}): Promise<`0x${string}` | undefined> {
  const { wagmiConfig, chainId, payer, expectedNonce, signal, preSendBlock } = opts
  const startBlock = await getBlockNumber(wagmiConfig, { chainId }).catch(() => null)
  // Anchor the walk to whichever is OLDER: the pre-send block (authoritative
  // when present) or `startBlock - 50` (defensive fallback for fast chains
  // when we couldn't capture the pre-send head). 50-block buffer covers ~100s
  // on Base / 12s on Arbitrum / 10min on mainnet — plenty for a wallet UI
  // delay even on the slowest path.
  let walkFrom: bigint | null = null
  if (preSendBlock != null) {
    walkFrom = preSendBlock - 1n
  } else if (startBlock != null) {
    walkFrom = startBlock - 50n
  }
  while (!signal.aborted) {
    await new Promise(r => setTimeout(r, 3000))
    if (signal.aborted) return undefined
    let latestNonce: number
    try {
      latestNonce = await getTransactionCount(wagmiConfig, {
        address: payer, blockTag: 'latest', chainId,
      })
    } catch {
      continue
    }
    if (latestNonce <= expectedNonce) continue

    const head = await getBlockNumber(wagmiConfig, { chainId }).catch(() => null)
    if (head == null) continue
    const fromBlock = walkFrom ?? head - 25n
    walkFrom = head + 1n
    for (let bn = fromBlock; bn <= head; bn++) {
      if (signal.aborted) return undefined
      let txs: Array<{ from: string; nonce: number; hash: string }> = []
      try {
        const block = await getBlock(wagmiConfig, {
          blockNumber: bn, includeTransactions: true, chainId,
        })
        txs = (block?.transactions as Array<{ from: string; nonce: number; hash: string }>) ?? []
      } catch {
        continue
      }
      const match = txs.find(
        t => t?.from?.toLowerCase() === payer.toLowerCase() && Number(t?.nonce) === expectedNonce
      )
      if (match?.hash) return match.hash as `0x${string}`
    }
  }
  return undefined
}

export function CheckoutStep({
  config,
  options,
  ethAvailable,
  ethDisabledReason,
  ethPriceUsd,
  chainMetadata,
  onConfirmed,
}: {
  config: WCConfig
  options: PaymentOption[]
  ethAvailable: boolean
  ethDisabledReason: string | null
  ethPriceUsd: number | null
  chainMetadata: Record<string, { name: string; explorer_url: string }>
  onConfirmed: (txHash: string, quote: Quote) => void
}) {
  const [tokenFilter, setTokenFilter] = useState<string | null>(null)
  const [picked, setPicked] = useState<PaymentOption | null>(null)

  // Persist the buyer's pick to sessionStorage keyed by orderCode. Survives
  // a full page reload (iOS Safari can evict the WebView while the wallet
  // app is in foreground during signMessage; mobile Coinbase / Base
  // Account deep-link round-trips trigger this). Stored as
  // `{chain_id, symbol}` identity only — we re-attach to the live
  // PaymentOption on restore so we don't carry stale server-side fields
  // (rates, addresses) across reloads. Scoped to sessionStorage so it
  // never leaks across orders and clears with the tab.
  const pickStorageKey = `wc-pick:${config.orderCode}`

  // Persist the broadcast tx (hash + the quote it was paid against) the
  // instant the wallet returns a hash, keyed by orderCode. If the tab
  // reloads/crashes between broadcast and verify (common when the buyer
  // thinks it's stuck and refreshes), we recover this on mount and resume
  // verification of the EXISTING tx instead of landing them on a fresh
  // Pay button — the double-pay trap. Cleared on verified success.
  const txStorageKey = `wc-tx:${config.orderCode}`
  const persistTx = (q: Quote, hash: string) => {
    try {
      window.sessionStorage.setItem(txStorageKey, JSON.stringify({ txHash: hash, quote: q }))
    } catch { /* storage unavailable — best effort */ }
  }
  const clearPersistedTx = () => {
    try { window.sessionStorage.removeItem(txStorageKey) } catch { /* ignore */ }
  }

  // Combined hydrate-or-default: try restoring from sessionStorage first,
  // and only fall back to ETH auto-select if no saved pick matches a
  // currently-offered option. Replaces the original auto-select effect;
  // guard `if (tokenFilter !== null || picked !== null) return` still
  // prevents clobbering an explicit user choice on re-render.
  useEffect(() => {
    if (tokenFilter !== null || picked !== null) return
    if (options.length === 0) return

    try {
      const raw = window.sessionStorage.getItem(pickStorageKey)
      if (raw) {
        const saved = JSON.parse(raw) as { chain_id?: number; symbol?: string }
        const match = options.find(
          o => o.chain_id === saved.chain_id && o.symbol === saved.symbol,
        )
        if (match) {
          setTokenFilter(match.symbol)
          setPicked(match)
          return
        }
      }
    } catch {
      // Storage unavailable (Private Browsing) or malformed JSON — fall through
    }

    // Pre-select ETH when payment options first arrive — saves the user a click
    // for the most common case. Falls back to leaving everything unselected if
    // ETH isn't offered (oracle divergence, chain disabled, etc.); the user
    // picks an asset manually then.
    const firstEth = options.find(o => o.symbol === 'ETH')
    if (!firstEth) return
    setTokenFilter('ETH')
    setPicked(firstEth)
  }, [options, tokenFilter, picked, pickStorageKey])

  // Mirror the current pick to sessionStorage on every change. Reactive
  // useEffect catches normal state transitions; the pagehide/visibility
  // listener below catches the case where iOS kills the WebView mid-flow
  // before React's commit phase had a chance to fire.
  useEffect(() => {
    try {
      if (picked) {
        window.sessionStorage.setItem(
          pickStorageKey,
          JSON.stringify({ chain_id: picked.chain_id, symbol: picked.symbol }),
        )
      } else {
        window.sessionStorage.removeItem(pickStorageKey)
      }
    } catch {
      // Storage unavailable — non-fatal, just lose reload-persistence
    }
  }, [picked, pickStorageKey])

  // Belt-and-braces flush on iOS Safari WebView eviction. When the wallet
  // app takes foreground via Universal Link, iOS may discard the
  // background tab under memory pressure — neither `unload` nor
  // `beforeunload` fire reliably in that path, but `pagehide` and
  // `visibilitychange→hidden` do (MDN: pagehide, WebKit blog 14403).
  // Persisting synchronously here means the buyer's pick survives even
  // if React hasn't run its commit phase yet.
  useEffect(() => {
    const flush = () => {
      if (!picked) return
      try {
        window.sessionStorage.setItem(
          pickStorageKey,
          JSON.stringify({ chain_id: picked.chain_id, symbol: picked.symbol }),
        )
      } catch {
        // Best-effort
      }
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    window.addEventListener('pagehide', flush)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('pagehide', flush)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [picked, pickStorageKey])
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)
  // Subject + body of the support email displayed in a copy-paste popup
  // when any "Contact support" / "Email the event organizer" link is
  // clicked. Set alongside opening the mailto so users without a
  // configured mail client still have a path to send the message.
  const [supportPopup, setSupportPopup] = useState<{ subject: string; body: string; mailto: string } | null>(null)
  // Tx hash captured when verify succeeds — drives the inline success card.
  // We render the success view inside CheckoutStep (not via a separate
  // SuccessStep swap) so the buyer stays in the same visual frame the whole
  // time: same wrapper, same WalletHeader, just the picker swapped for a
  // confirmation card. Avoids the jarring view replacement at the moment of
  // success.
  const [confirmedTxHash, setConfirmedTxHash] = useState<string | null>(null)
  // Tx hash captured as soon as the wallet returns it (post-broadcast, pre-
  // verification). Lets the "Amount: X to ADDRESS" line swap to a clickable
  // explorer link while the user waits for the backend's confirmation poll
  // — same hash that will land on the success card, just surfaced earlier.
  // Preserved across `verifying` → `error` so a verify failure still lets
  // the buyer inspect the onchain state.
  const [pendingTxHash, setPendingTxHash] = useState<string | null>(null)

  // Pre-fetched challenge so `handlePay` doesn't have to do a network
  // round-trip before opening the wallet. iOS Safari (and Coinbase /
  // Base Account's keys.coinbase.com popup on desktop) require the
  // first wallet RPC to fire inside the user-gesture window — any
  // intervening `await fetch(...)` consumes the gesture token and the
  // popup is blocked. The challenge is per-order (only `order_code` +
  // `order_secret` are sent), not per-chain/token, so we can fetch it
  // once at mount and reuse across pick changes. Stale nonces are
  // handled by the `STALE_MS` check in handlePay — if the user idles
  // past the TTL we fall back to inline fetch (one wallet popup will
  // be blocked but it's a long-idle case the buyer can retry).
  const [prefetchedChallenge, setPrefetchedChallenge] = useState<{
    nonce: string
    message: string
    fetchedAt: number
  } | null>(null)
  // Confirmation progress surfaced from the backend's `confirmations` /
  // `confirmations_required` fields. Used to render "Confirming onchain
  // (X/N)" instead of an opaque spinner during the verify poll.
  const [confirmProgress, setConfirmProgress] = useState<{ current: number; required: number } | null>(null)
  // Timestamp (ms) until which the verify poll is in rate-limit backoff.
  // Drives the calm "Network's busy — retrying in Ns" cooldown copy so a
  // rate-limited (but already-paid) buyer sees a countdown, not a spinner
  // that looks stuck. Null when not cooling down. `nowMs` ticks every
  // second while a cooldown is active so the countdown actually counts.
  const [verifyCooldownUntil, setVerifyCooldownUntil] = useState<number | null>(null)
  const [nowMs, setNowMs] = useState(() => Date.now())
  useEffect(() => {
    if (verifyCooldownUntil == null) return
    setNowMs(Date.now())
    const id = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [verifyCooldownUntil])
  const cooldownRemaining = verifyCooldownUntil
    ? Math.max(0, Math.ceil((verifyCooldownUntil - nowMs) / 1000))
    : 0

  // Safe (multisig) detection state — populated by the post-`useAccount`
  // effect below. Declared here so the recovery / picker render paths
  // can reference `isSafeAddress` without a forward-ref dance.
  const [isSafeAddress, setIsSafeAddress] = useState(false)
  const [safeThreshold, setSafeThreshold] = useState<number | null>(null)

  // Hash-recovery escape hatch. Some wallets (Binance Wallet macOS;
  // intermittently Bitget Mobile / TokenPocket) broadcast the tx but never
  // return the hash via WC, leaving sendTransactionAsync hanging forever.
  // The recovery wrapper races wallet vs nonce-discovery vs manual paste.
  const [recoveryStatus, setRecoveryStatus] = useState<null | 'discovery' | 'manual'>(null)
  const [manualHashInput, setManualHashInput] = useState('')
  const [manualHashError, setManualHashError] = useState<string | null>(null)
  const [manualHashSubmitting, setManualHashSubmitting] = useState(false)
  const manualHashResolverRef = useRef<((hash: `0x${string}`) => void) | null>(null)
  // Captured at recovery start so submitManualHash can validate the pasted
  // hash against the right payer + expected nonce before accepting it.
  const expectedTxRef = useRef<{ payer: string; chainId: number; expectedNonce: number | undefined } | null>(null)

  // ── DEBUG: tx-hash recovery simulation ──
  // Console-gated developer affordance. The panel is hidden by default —
  // type `wcDebug()` in the browser console to flip `debugEnabled` and
  // expose three radio modes that force the recovery wrapper down a
  // specific path without rebuilding:
  //   normal: wallet returns hash → WALLET path wins
  //   no-hash: wallet hash is discarded → DISCOVERY path should win
  //   no-hash-no-discovery: discovery also stubbed → MANUAL path is the only way
  const [simulateMode, setSimulateMode] = useState<'normal' | 'no-hash' | 'no-hash-no-discovery'>('normal')
  const [debugEnabled, setDebugEnabled] = useState(false)

  // ── DEBUG: rate-limit simulation ──
  // When on, `pollVerify` synthesizes a 429 on every iteration WITHOUT
  // hitting the server, so QA can watch the backoff + verify-only recovery
  // behave under sustained rate limiting. Toggle live (mid-verify) from the
  // debug panel checkbox or the console: `wcSimulateRateLimit(true|false)`.
  // A ref backs it so an in-flight pollVerify loop sees the change without
  // being re-created; the state mirror just drives the checkbox.
  const [simulateRateLimit, setSimulateRateLimit] = useState(false)
  const simulateRateLimitRef = useRef(false)
  const setSimRateLimit = (on: boolean) => {
    simulateRateLimitRef.current = on
    setSimulateRateLimit(on)
  }

  // Expose the toggle on the window so devs can flip the panel from
  // DevTools without a page reload. Two aliases (`wcDebug` and `wcdebug`)
  // for ergonomics — different muscle memory between developers.
  // We use a namespaced name (NOT `window.debug`) because Chrome's
  // DevTools console already binds `debug(fn)` as a function-breakpoint
  // utility — typing `debug` alone there resolves to Chrome's version,
  // not anything we set on window.
  useEffect(() => {
    type WinWithDebug = Window & {
      wcDebug?: () => string
      wcdebug?: () => string
      wcSimulateRateLimit?: (on?: boolean) => string
    }
    const w = window as unknown as WinWithDebug
    const toggle = () => {
      setDebugEnabled((prev) => !prev)
      return '[wc_inject] debug panel toggled'
    }
    // `wcSimulateRateLimit()` flips, `wcSimulateRateLimit(true/false)` sets.
    const simRl = (on?: boolean) => {
      const next = typeof on === 'boolean' ? on : !simulateRateLimitRef.current
      setSimRateLimit(next)
      return `[wc_inject] simulate rate limit: ${next ? 'ON' : 'OFF'}`
    }
    w.wcDebug = toggle
    w.wcdebug = toggle
    w.wcSimulateRateLimit = simRl
    return () => {
      delete w.wcDebug
      delete w.wcdebug
      delete w.wcSimulateRateLimit
    }
  }, [])

  const { address, chainId: walletChainId, connector } = useAccount()
  const { walletInfo } = useWalletInfo()
  const connectionKind = classifyConnection(connector)
  const connectedWalletName = walletInfo?.name || connector?.name
  const { signMessageAsync } = useSignMessage()
  const { switchChainAsync, switchChain } = useSwitchChain()

  // Safe (multisig) onchain probe — opt-in per event via
  // `config.safePaymentsEnabled`. Sets `isSafeAddress` when Safe Tx
  // Service confirms the connected address is a Safe and surfaces the
  // signers-required threshold for the multi-signer notice.
  useEffect(() => {
    if (!config.safePaymentsEnabled) {
      dbg('safe:probe:skipped', { reason: 'flag-off' })
      setIsSafeAddress(false)
      setSafeThreshold(null)
      return
    }
    if (!address || !walletChainId) {
      dbg('safe:probe:skipped', { reason: 'no-account-yet', hasAddress: !!address, walletChainId })
      setIsSafeAddress(false)
      setSafeThreshold(null)
      return
    }
    let cancelled = false
    dbg('safe:probe:start', { address, chainId: walletChainId })
    probeSafe(walletChainId, address).then(r => {
      if (cancelled) return
      dbg('safe:probe:done', {
        address,
        chainId: walletChainId,
        isSafe: r.isSafe,
        threshold: r.isSafe ? r.threshold : null,
      })
      if (r.isSafe) {
        setIsSafeAddress(true)
        setSafeThreshold(r.threshold)
      } else {
        setIsSafeAddress(false)
        setSafeThreshold(null)
      }
    })
    return () => { cancelled = true }
  }, [config.safePaymentsEnabled, address, walletChainId])

  /** Heuristic OR onchain confirmation — either is enough to take the
   *  Safe send + sign-poll path. The heuristic now includes
   *  `connectedWalletName` because Reown's WC Safe entry comes through
   *  with the generic `walletConnect` connector type; the actual brand
   *  ("Safe{Wallet}", "Safe Apps") only appears on `useWalletInfo().name`.
   *  Gated by the admin flag so a missing toggle leaves the flow exactly
   *  where it was before this work. */
  const isSafePath = !!config.safePaymentsEnabled && (isSafeWallet(connector, connectedWalletName) || isSafeAddress)

  // Fire-and-forget chain switch on user-initiated pick. Mirrors the
  // storefront's `selectPaymentOption` behavior — by the time the buyer
  // taps Pay the wallet is usually already on the target chain.
  // SKIPPED for Coinbase / Base Smart Wallet: calling switchChain there
  // trips the CB SDK desync bug (wagmi state advances but the connector's
  // getChainId() stays stale → ConnectorChainMismatchError later). CBSW
  // is multi-chain and signs on any chain via the EIP-5792 sendCalls path
  // (which passes chainId explicitly), so no prior switch is ever needed.
  function pickAndMaybeSwitch(opt: PaymentOption) {
    setPicked(opt)
    if (connectionKind === 'coinbaseWallet') return
    // Safes are chain-scoped per deployment; `wallet_switchEthereumChain`
    // is meaningless (the Safe app is already on whichever chain the
    // buyer opened it on). Skip the prompt — if the picked chain differs
    // from the Safe's chain, the send step will surface a friendlier
    // error than the wallet's "unsupported method" response.
    if (connectionKind === 'safe' || isSafePath) return
    if (walletChainId !== opt.chain_id && switchChain) {
      switchChain({ chainId: opt.chain_id })
    }
  }
  const { writeContractAsync } = useWriteContract()
  const { sendTransactionAsync } = useSendTransaction()

  // Pull per-(chain, token) balances for the connected wallet so we can show
  // them in the picker and grey out rows the user can't afford. Plugin uses
  // Zapper-first / RPC-fallback (same engine the x402 endpoint uses).
  // Poll only while the buyer is choosing (idle) or retrying (error); once
  // they commit to pay we stop the interval to avoid needless 429 pressure
  // (the manual refresh button still works via .refetch()).
  const balancesQuery = useWalletBalances(config, address, status === 'idle' || status === 'error')

  // For each option, compute the raw amount expected at the order's USD total.
  // Stables: total_usd × 10^6 (both USDC and USDT0 are 6-dec USD-pegged).
  // ETH: uses `ethPriceUsd` from the payment-options response — the same
  // dual-oracle (Coinbase + Binance) value the quote-creation endpoint uses,
  // so the picker's sufficiency check matches what the server will accept.
  // The actual quote-time check remains authoritative; this is just a
  // pre-flight filter so users with clearly-empty wallets see it early.
  const totalUsdFloat = parseFloat(config.orderTotalUsd || '0') || 0
  function expectedRaw(symbol: string): bigint | null {
    if (!totalUsdFloat) return null
    if (symbol === 'USDC' || symbol === 'USDT0') {
      // Round up so we don't say "sufficient" when the user has exactly $X − 1 wei.
      return BigInt(Math.ceil(totalUsdFloat * 1e6))
    }
    if (symbol === 'ETH') {
      // No price means oracles diverged or were unreachable — the ETH option
      // would already be filtered out upstream, but skip the check defensively.
      if (!ethPriceUsd || ethPriceUsd <= 0) return null
      return BigInt(Math.ceil((totalUsdFloat / ethPriceUsd) * 1e18))
    }
    return null
  }
  // Use the wagmi `config` imperatively via `waitForTransactionReceipt` so we
  // can target the quote's chainId explicitly. Necessary because the user's
  // wallet may have been on a different chain when this component mounted;
  // a chain-scoped hook captured at render time would query the wrong RPC.
  const wagmiConfig = useConfig()

  const { organizer, event } = { organizer: config.organizer, event: config.event }

  // ── Challenge prefetch ──
  // Fire-and-forget on connect so `handlePay`'s first await can be
  // `signMessageAsync(...)` rather than `await fetch('/challenge/')`.
  // Critical for iOS Safari and the keys.coinbase.com popup on desktop:
  // user-gesture tokens don't survive a network round-trip, and without
  // a gesture the wallet open is blocked. Re-fires whenever the
  // connected address changes (reconnect, account switch) so the nonce
  // we hand the user is always tied to the wallet they're paying from.
  useEffect(() => {
    if (!address) return
    let cancelled = false
    ;(async () => {
      try {
        const cr = await fetch(`${config.urlPrefix}/challenge/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            order_code: config.orderCode,
            order_secret: config.orderSecret,
            organizer,
            event,
          }),
        })
        if (!cr.ok) return // pre-fetch failed → handlePay falls back to inline fetch
        const body = (await cr.json()) as { nonce?: string; message?: string }
        if (cancelled || !body.nonce || !body.message) return
        setPrefetchedChallenge({
          nonce: body.nonce,
          message: body.message,
          fetchedAt: Date.now(),
        })
      } catch {
        // Best-effort prefetch; silent failure → inline fetch later.
      }
    })()
    return () => { cancelled = true }
  }, [address, config.urlPrefix, config.orderCode, config.orderSecret, organizer, event])

  // ── Client-info telemetry beacon ──
  // Reports which wallet brand + connection type buyers use, in two
  // phases (greppable separately as `[wc-client] phase=connect` and
  // `phase=pay`): once when a wallet connects, and once when the buyer
  // initiates payment. sendBeacon is fire-and-forget and survives the
  // user navigating away; params ride in the URL query so they land in
  // both the access log and the app log (server reads request.GET on the
  // POST beacon). Telemetry must never break checkout, so everything is
  // wrapped and failures are swallowed.
  const sendClientInfo = useCallback((phase: 'connect' | 'pay') => {
    if (!address) return
    try {
      const params = new URLSearchParams({
        phase,
        organizer,
        event,
        order_code: config.orderCode,
        wallet_name: connectedWalletName || '',
        connection_kind: connectionKind,
        // Wallet's currently-active chain vs the chain the buyer picked to
        // pay on. A mismatch is the tell-tale of a needed chain switch,
        // the most common "internal error" cause for mobile wallets.
        wallet_chain: walletChainId != null ? String(walletChainId) : '',
        picked_chain: picked ? String(picked.chain_id) : '',
        picked_token: picked ? picked.symbol : '',
        is_safe: isSafePath ? '1' : '0',
        plugin_version: config.pluginVersion || '',
        address,
        ua: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      })
      const url = `${config.urlPrefix}/client-info/?${params.toString()}`
      if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
        navigator.sendBeacon(url)
      } else {
        fetch(url, { method: 'POST', credentials: 'same-origin', keepalive: true }).catch(() => {})
      }
    } catch {
      // swallow — telemetry is best-effort
    }
  }, [address, connectedWalletName, connectionKind, walletChainId, picked, isSafePath, config.urlPrefix, config.orderCode, config.pluginVersion, organizer, event])

  // phase=connect: once per connected address (account switch re-logs).
  const clientInfoConnectRef = useRef<string | null>(null)
  useEffect(() => {
    if (!address) return
    if (clientInfoConnectRef.current === address) return
    clientInfoConnectRef.current = address
    sendClientInfo('connect')
  }, [address, sendClientInfo])

  // Pretix's native submit button is hidden via `body.wc-full-checkout`, which
  // is now owned by WCPaymentApp (covers all stages, not just checkout).

  async function pollVerify(q: Quote, txHash: string) {
    // Adaptive cadence: poll roughly every half-block-time for the chain.
    // Total budget covers `min_confirmations + 1` blocks of waiting.
    const interval = pollIntervalMs(q.chain_id)
    // We don't know the chain's required confs until the first response —
    // use an optimistic 3 as the budget upper-bound (matches typical configs).
    const initialBudget = pollMaxDurationMs(q.chain_id, 3)
    const startedAt = Date.now()
    let budget = initialBudget

    // Rate-limit backoff: grows on consecutive 429s, resets on any non-429
    // response. The tx is already mined and immutable at this point, so a
    // 429 here is NEVER a reason to bail to the error/Retry-pay state — we
    // just need to wait for a verify slot. We also extend `budget` by the
    // backoff wait so rate-limit time doesn't eat the confirmation budget
    // and strand a paid buyer on a "timed out" error.
    let rlBackoff = 0

    // Default exponential backoff (2s → 4s → 8s …, capped 30s) with jitter.
    const backoffMs = () => Math.min(30_000, 2_000 * Math.pow(2, rlBackoff)) + Math.floor(Math.random() * 1_000)

    // Shared rate-limit cooldown: surface a countdown to the UI, extend the
    // budget so the wait doesn't consume the confirmation window, sleep,
    // then clear the cooldown. The tx is already mined, so a 429 here is
    // never fatal — we just wait for a verify slot.
    const cooldownSleep = async (wait: number) => {
      rlBackoff += 1
      budget += wait
      setVerifyCooldownUntil(Date.now() + wait)
      await new Promise((r) => setTimeout(r, wait))
      setVerifyCooldownUntil(null)
    }

    try {
      while (Date.now() - startedAt < budget) {
        await new Promise((r) => setTimeout(r, interval))

        // DEBUG: synthesize a 429 without touching the server so QA can watch
        // the backoff + cooldown UI under sustained rate limiting. Toggle live
        // via `wcSimulateRateLimit(true|false)` or the debug panel checkbox.
        // No-op in prod (ref only set by the dev helper).
        if (simulateRateLimitRef.current) {
          const wait = backoffMs()
          dbgWarn('verify:rate-limited (SIMULATED)', { wait, attempt: rlBackoff + 1 })
          await cooldownSleep(wait)
          continue
        }

        const r = await fetch(`${config.urlPrefix}/verify/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            quote_id: q.quote_id, tx_hash: txHash, chain_id: q.chain_id,
            organizer, event,
          }),
        })
        if (r.ok) {
          rlBackoff = 0
          const body = await r.json()
          if (body.verified) {
            setConfirmProgress(null)
            return
          }
        } else if (r.status === 429) {
          // Honor server Retry-After if present, else exponential backoff.
          const retryAfterHeader = parseInt(r.headers.get('Retry-After') || '', 10)
          const wait = Number.isFinite(retryAfterHeader) && retryAfterHeader > 0
            ? retryAfterHeader * 1000
            : backoffMs()
          dbgWarn('verify:rate-limited', { wait, attempt: rlBackoff + 1 })
          await cooldownSleep(wait)
        } else {
          const body = await r.json().catch(() => ({} as { error?: string; confirmations?: number | null; confirmations_required?: number | null }))
          const errMsg = (body.error as string | undefined) || `verify HTTP ${r.status}`
          // Defensive: some deployments surface the rate limit as a string
          // body rather than a 429 status — treat that as retryable too.
          const isRateLimit = errMsg.toLowerCase().includes('rate limit')
          if (isRateLimit) {
            await cooldownSleep(backoffMs())
            continue
          }
          rlBackoff = 0
          if (!RETRYABLE_ERROR_SUBSTRINGS.some((s) => errMsg.includes(s))) {
            setConfirmProgress(null)
            throw new Error(errMsg)
          }
          // Update progress + recompute budget once we know the chain's threshold.
          const cur = typeof body.confirmations === 'number' ? body.confirmations : null
          const req = typeof body.confirmations_required === 'number' ? body.confirmations_required : null
          if (cur !== null && req !== null) {
            setConfirmProgress({ current: cur, required: req })
            budget = pollMaxDurationMs(q.chain_id, req) + (budget - initialBudget)
          }
        }
      }
      setConfirmProgress(null)
      throw new Error('Verification timed out. Try submitting the transaction hash manually below.')
    } finally {
      // Never leave a stale cooldown countdown on screen after the poll ends.
      setVerifyCooldownUntil(null)
    }
  }

  // ── Send-with-recovery ──
  // Wraps the wallet's send call (sendTransactionAsync for ETH,
  // writeContractAsync for ERC20) so wallets that broadcast but fail to
  // return the hash via WC don't strand the UI. Three paths race:
  //   1. Wallet → returns hash via WC/injected (the happy path)
  //   2. Nonce-discovery → after 20s grace, walks blocks looking for any
  //      mined tx from `payer` at `expectedNonce`. Up to 60s total.
  //   3. Manual hash entry → after the auto window expires, an input
  //      surfaces so the buyer can paste the hash from their wallet.
  async function sendWithRecovery(args: {
    walletSend: () => Promise<string>
    payer: `0x${string}`
    chainId: number
    expectedNonce: number | undefined
  }): Promise<`0x${string}`> {
    expectedTxRef.current = { payer: args.payer, chainId: args.chainId, expectedNonce: args.expectedNonce }

    // Snapshot the chain head BEFORE asking the wallet to sign. The block
    // walk in discoverTxByNonce uses this as the lower bound — without it,
    // the anchor defaults to discovery-start (post-grace), missing any tx
    // that mined while the user was still confirming. On fast chains (Base,
    // Arbitrum) the gap is easily 15–25 blocks and discovery silently fails.
    let preSendBlock: bigint | undefined
    try {
      preSendBlock = await getBlockNumber(wagmiConfig, { chainId: args.chainId })
    } catch {
      preSendBlock = undefined
    }

    const startedAt = Date.now()
    let resolved = false
    let resolveOuter!: (h: `0x${string}`) => void
    let rejectOuter!: (e: unknown) => void
    const result = new Promise<`0x${string}`>((res, rej) => {
      resolveOuter = res
      rejectOuter = rej
    })
    const discoverySignal = { aborted: false }

    const cleanup = () => {
      manualHashResolverRef.current = null
      setRecoveryStatus(null)
      discoverySignal.aborted = true
    }
    const finishFromWallet = (h: `0x${string}`) => {
      if (resolved) return
      resolved = true
      // eslint-disable-next-line no-console
      console.info('[wc_inject] tx-hash recovery: WALLET path won', { hash: h, elapsedMs: Date.now() - startedAt })
      cleanup()
      resolveOuter(h)
    }
    const finishFromRecovery = (h: `0x${string}`, source: 'discovery' | 'manual') => {
      if (resolved) return
      resolved = true
      // eslint-disable-next-line no-console
      console.info(`[wc_inject] tx-hash recovery: ${source.toUpperCase()} path won`, { hash: h, elapsedMs: Date.now() - startedAt })
      cleanup()
      resolveOuter(h)
    }
    const fail = (e: unknown) => {
      if (resolved) return
      resolved = true
      // eslint-disable-next-line no-console
      console.info('[wc_inject] tx-hash recovery: WALLET path FAILED', { error: e, elapsedMs: Date.now() - startedAt })
      cleanup()
      rejectOuter(e)
    }
    manualHashResolverRef.current = (h) => finishFromRecovery(h, 'manual')

    // Path 1: the wallet. If simulating a no-hash bug, broadcast goes through
    // (the wallet still signs and broadcasts) but we discard the returned hash
    // so the wrapper has to fall back to discovery / manual entry.
    const simulating = simulateMode !== 'normal'
    args.walletSend()
      .then(h => {
        if (simulating) {
          // eslint-disable-next-line no-console
          console.warn('[SIMULATE] discarding wallet hash so recovery has to take over:', h)
          return
        }
        finishFromWallet(h as `0x${string}`)
      })
      .catch(e => fail(e))

    // Path 2 + 3: discovery (after grace) + manual fallback (after total)
    const GRACE_MS = 20_000
    const TOTAL_MS = 60_000

    // Discovery only meaningful when we know the broadcast nonce. Without it
    // we'd be guessing — surface the manual path immediately on timeout.
    // Skipped entirely when simulating "no discovery" so we can test the
    // manual-entry path without waiting for real chain data to fail.
    const stubDiscovery = simulateMode === 'no-hash-no-discovery'
    if (args.expectedNonce !== undefined && !stubDiscovery) {
      setTimeout(async () => {
        if (resolved) return
        // eslint-disable-next-line no-console
        console.info('[wc_inject] tx-hash recovery: discovery polling started', { graceMs: GRACE_MS, totalMs: TOTAL_MS, expectedNonce: args.expectedNonce })
        setRecoveryStatus('discovery')
        try {
          const found = await discoverTxByNonce({
            wagmiConfig,
            chainId: args.chainId,
            payer: args.payer,
            expectedNonce: args.expectedNonce!,
            signal: discoverySignal,
            preSendBlock,
          })
          if (found) {
            finishFromRecovery(found, 'discovery')
            return
          }
        } catch (err) {
          // eslint-disable-next-line no-console
          console.info('[wc_inject] tx-hash recovery: discovery error', err)
        }
      }, GRACE_MS)
    } else if (stubDiscovery) {
      setTimeout(() => {
        if (resolved) return
        // eslint-disable-next-line no-console
        console.warn('[SIMULATE] discovery stubbed — manual entry will surface at TOTAL_MS')
        setRecoveryStatus('discovery')
      }, GRACE_MS)
    }

    setTimeout(() => {
      if (resolved) return
      // eslint-disable-next-line no-console
      console.info('[wc_inject] tx-hash recovery: auto window exhausted, surfacing manual hash entry')
      // Stop the discovery walker too — manual entry is the buyer's call now.
      discoverySignal.aborted = true
      setRecoveryStatus('manual')
    }, TOTAL_MS)

    return result
  }

  // ── Manual-hash submit ──
  // Validates the pasted hash onchain (from=payer, nonce=expectedNonce
  // when available) before accepting and resolving the recovery promise.
  async function submitManualHash() {
    const raw = manualHashInput.trim()
    setManualHashError(null)
    if (!/^0x[0-9a-fA-F]{64}$/.test(raw)) {
      setManualHashError('That doesn’t look like a transaction hash. It should be 0x followed by 64 hex characters.')
      return
    }
    if (!expectedTxRef.current || !manualHashResolverRef.current) {
      setManualHashError('No payment is currently waiting for a hash.')
      return
    }
    const expected = expectedTxRef.current
    setManualHashSubmitting(true)
    try {
      const tx = await getTransaction(wagmiConfig, { hash: raw as `0x${string}`, chainId: expected.chainId })
      if (!tx) {
        setManualHashError('Transaction not found on chain. Make sure you pasted the correct hash and that it has been broadcast.')
        return
      }
      if ((tx.from ?? '').toLowerCase() !== expected.payer.toLowerCase()) {
        setManualHashError('That transaction was sent from a different wallet than the one connected here.')
        return
      }
      if (expected.expectedNonce !== undefined && Number(tx.nonce) !== expected.expectedNonce) {
        setManualHashError('That transaction’s nonce does not match the order. Make sure you pasted the hash for THIS payment, not a previous one.')
        return
      }
      manualHashResolverRef.current(raw as `0x${string}`)
      setManualHashInput('')
    } catch (e) {
      setManualHashError(
        (e instanceof Error && e.message) ||
        'Could not look up the transaction. Please try again in a moment.'
      )
    } finally {
      setManualHashSubmitting(false)
    }
  }

  async function handlePay() {
    if (!picked || !address) return
    setError(null)
    // phase=pay telemetry — fired here (not on every status change) so it
    // marks an actual payment attempt, distinct from phase=connect.
    sendClientInfo('pay')
    // Clear any hash from a previous attempt so the in-progress UI doesn't
    // show a stale "View transaction" link until this attempt has its own.
    setPendingTxHash(null)

    dbg('handlePay:start', {
      pluginVersion: config.pluginVersion,
      connectionKind,
      connectedWalletName,
      address,
      walletChainId,
      pickedChainId: picked.chain_id,
      pickedChainName: picked.chain_name,
      pickedSymbol: picked.symbol,
      orderCode: config.orderCode,
      hasPrefetchedChallenge: !!prefetchedChallenge,
      prefetchedChallengeAgeMs: prefetchedChallenge
        ? Date.now() - prefetchedChallenge.fetchedAt
        : null,
      isSafePath,
      isSafeAddress,
      safeThreshold,
    })

    try {
      // ── Step 1: Get challenge (prefetched-or-inline) ──
      //
      // The prefetch effect fires on connect, so by the time the buyer
      // clicks Pay we usually already have a fresh `{nonce, message}` in
      // state. Using it here means the *first* await in this click
      // handler is `signMessageAsync` — which preserves the iOS Safari
      // user-gesture token and unblocks the wallet popup on mobile
      // (and the keys.coinbase.com popup on desktop Base Account).
      //
      // STALE_MS bounds how long we trust a prefetched nonce. Plugin's
      // challenge nonce TTL is conservative (minutes), so 4 minutes
      // leaves a comfortable safety margin without risking the server
      // rejecting a stale nonce mid-flow. If the prefetch is stale or
      // missing we fall back to inline fetch — one wallet popup may
      // get blocked on iOS in that path, but it's a "buyer idled for
      // minutes" case they can retry.
      const STALE_MS = 4 * 60 * 1000
      let nonce: string
      let message: string
      let challengeSource: 'prefetched' | 'inline'
      if (
        prefetchedChallenge &&
        Date.now() - prefetchedChallenge.fetchedAt < STALE_MS
      ) {
        nonce = prefetchedChallenge.nonce
        message = prefetchedChallenge.message
        challengeSource = 'prefetched'
      } else {
        setStatus('challenge')
        const cr = await fetch(`${config.urlPrefix}/challenge/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            order_code: config.orderCode, order_secret: config.orderSecret,
            organizer, event,
          }),
        })
        if (!cr.ok) {
          const body = await cr.json().catch(() => ({}))
          dbgErr('challenge:http', { status: cr.status, body })
          throw new Error(body.error || `challenge HTTP ${cr.status}`)
        }
        const body = await cr.json()
        nonce = body.nonce
        message = body.message
        challengeSource = 'inline'
      }
      dbg('challenge:ready', { source: challengeSource, nonce })

      // Step 2: Sign challenge.
      // First wallet RPC of the click chain — gesture token must still
      // be alive here on iOS. Don't insert any awaits between the click
      // entry and this call.
      //
      // For Coinbase / Base Smart Wallet we bypass wagmi's signMessage
      // wrapper for the same reason the capability probe needs bypassing:
      // wagmi's mutation calls `getConnectorClient` with default
      // `assertChainId: true`, and the CB SDK desync (connector reports
      // 1 while connection is 10) makes that assertion throw before the
      // wallet ever sees the request. personal_sign is chain-agnostic on
      // the RPC level — we just need to skip the assertion. Other
      // wallets use the wagmi hook path unchanged.
      setStatus('signing-challenge')
      let signature: string
      if (connectionKind === 'coinbaseWallet') {
        const signClient = await getConnectorClient(wagmiConfig, {
          assertChainId: false,
          account: address as `0x${string}`,
        })
        signature = await viemSignMessage(signClient, {
          message,
          account: address as `0x${string}`,
        })
      } else {
        signature = await signMessageAsync({ message })
      }
      dbg('sign:done', {
        signatureLength: signature.length,
        signingChainId: walletChainId,
        path: connectionKind === 'coinbaseWallet' ? 'viem-bypass' : 'wagmi',
      })

      // Multi-sig Safe path: the wallet returns a 32-byte
      // safeMessageHash instead of a signature. Poll Safe Messages
      // Service until co-signers have signed and the API returns the
      // assembled ERC-1271 `preparedSignature` — that's what the
      // backend verifies via the Safe contract's isValidSignature.
      // Only enabled when `config.safePaymentsEnabled` is on.
      if (isSafePath && looksLikeSafeMessageHash(signature)) {
        setStatus('verifying')
        dbg('safe:messages:poll-start', { safeAddress: address, safeMessageHash: signature })
        signature = await pollSafeMessagesService(
          walletChainId,
          address as string,
          signature,
        )
        dbg('safe:messages:poll-done', { preparedSignatureLength: signature.length })
        setStatus('signing-challenge')
      }

      // The nonce we just signed is now consumed — clear the prefetched
      // copy so a retry (e.g. after a failed verify) goes through a
      // fresh challenge fetch instead of replaying a used nonce.
      setPrefetchedChallenge(null)

      // Step 3: Create quote.
      // `payer_address` is required for smart-wallet signatures (ERC-1271/6492 —
      // Coinbase/Base Smart Wallet, Safe, etc.) because those return contract-
      // level proofs that can't be ECDSA-recovered. For EOA signatures the
      // backend still recovers locally; sending the address both ways is fine.
      //
      // `signing_chain_id` is the chain the user's wallet was on at the moment
      // of signing — needed for CSW/Safe-style wallets because their ERC-1271
      // path wraps the hash with an EIP-712 domain separator that includes
      // the wallet's current chain_id. A CSW signature made on chain X only
      // validates when isValidSignature is called on chain X (other chains
      // rebuild a different domain separator and return 0xffffffff).
      setStatus('quoting')
      const qr = await fetch(`${config.urlPrefix}/create-quote/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          order_code: config.orderCode, order_secret: config.orderSecret,
          organizer, event,
          chain_id: picked.chain_id, symbol: picked.symbol,
          nonce, signature,
          payer_address: address,
          signing_chain_id: walletChainId,
        }),
      })
      if (!qr.ok) {
        const body = await qr.json().catch(() => ({}))
        // Stringify the error in the log so it's readable inline
        // without expanding the Object — quote:http errors are the
        // primary diagnostic for signature / chain mismatches.
        dbgErr('quote:http', {
          status: qr.status,
          errorMessage: typeof body?.error === 'string' ? body.error : undefined,
          body,
        })
        throw new Error(body.error || `create-quote HTTP ${qr.status}`)
      }
      const q: Quote = await qr.json()
      setQuote(q)
      dbg('quote:ready', {
        quoteId: q.quote_id,
        chainId: q.chain_id,
        symbol: q.symbol,
        amountRaw: q.amount_raw,
        receiveAddress: q.receive_address,
        expiresAt: q.expires_at,
      })

      // ── Step 4: Capability probe ──
      //
      // EIP-5792 (`wallet_sendCalls`) is the canonical 2026 path for
      // smart wallets and is what Base Account / Coinbase Smart Wallet
      // recommend. Compared to the legacy `switchChain` + `sendTransaction`
      // flow it has two material wins on the SW path:
      //   * the `chainId` parameter routes the request to the target chain
      //     in one prompt — no `wallet_switchEthereumChain` round-trip,
      //     which is the root cause of the desktop ConnectorChainMismatch
      //     bug (coinbase-wallet-sdk #1317).
      //   * the wallet returns a call-bundle id; we poll its status via
      //     `wallet_getCallsStatus` and get the onchain hash back, with
      //     no nonce-discovery race needed (sendWithRecovery exists to
      //     paper over wallets that broadcast but don't return the hash;
      //     5792's status RPC removes that failure mode by design).
      //
      // EOAs and older wallets don't implement 5792; viem's
      // `getCapabilities` returns `atomic.status` per chain — we treat
      // 'supported' / 'ready' as the green light to use the new path and
      // fall back to the legacy switch-then-send flow otherwise. Both
      // paths converge at `minedHash` → Step 7 verify.
      // Restrict 5792 to Coinbase / Base Account — that's the connector
      // class that has the chain-switch desync bug we're routing around.
      // MetaMask-over-WalletConnect returns capability shapes that can
      // pass the `atomic.status` check but its sendCalls implementation
      // isn't reliable when the WC session wasn't pre-scoped to the
      // target chain (regression: buyer rejects on what looks like a
      // confused tx prompt). Other wallets stay on the legacy path —
      // it's been working for them and doesn't need replacing.
      let atomicSupported = false
      if (connectionKind === 'coinbaseWallet') {
        try {
          // Bypass wagmi's getCapabilities wrapper — it goes through
          // getConnectorClient with the default `assertChainId: true`,
          // which trips the CB SDK desync bug (the very bug we use 5792
          // to route around). Pull a chain-bound client ourselves with
          // assertChainId disabled and call viem's primitive directly.
          const client = await getConnectorClient(wagmiConfig, {
            assertChainId: false,
            chainId: q.chain_id,
            account: address as `0x${string}`,
          })
          const caps = await viemGetCapabilities(client, { chainId: q.chain_id })
          const status = (caps as { atomic?: { status?: string } })?.atomic?.status
          atomicSupported = status === 'supported' || status === 'ready'
          dbg('capabilities:probed', { atomicStatus: status, atomicSupported })
        } catch (e) {
          dbgWarn('capabilities:failed', { error: (e as Error).message })
          // Capabilities RPC missing — fall through to legacy.
        }
      }
      dbg('path:chosen', { atomicSupported, path: atomicSupported ? '5792' : 'legacy' })

      let minedHash: string

      if (atomicSupported) {
        // ── 5792 path (Base Account / CB Smart Wallet / modern wallets) ──
        setStatus('signing-tx')

        // Build the single-call array. For ETH it's a plain value
        // transfer; for ERC20 we encode the ABI directly so viem's
        // generic `Calls` shape is happy (its writeContract overload
        // wants a chain-typed client).
        const callTo = q.symbol === 'ETH'
          ? {
              to: q.receive_address as `0x${string}`,
              value: BigInt(q.amount_raw),
            }
          : (() => {
              if (!q.token_address) throw new Error('token_address missing')
              return {
                to: q.token_address as `0x${string}`,
                data: encodeFunctionData({
                  abi: erc20Abi,
                  functionName: 'transfer',
                  args: [q.receive_address as `0x${string}`, BigInt(q.amount_raw)],
                }),
              }
            })()

        dbg('sendCalls:invoke', { chainId: q.chain_id, callCount: 1 })
        const { id } = await sendCalls(wagmiConfig, {
          chainId: q.chain_id,
          account: address as `0x${string}`,
          calls: [callTo],
        })
        dbg('sendCalls:returned', { id })

        // Poll the wallet's `wallet_getCallsStatus` until the bundle is
        // mined. Same bypass as the capability probe — wagmi's wrapper
        // would re-assert chain via getConnectorClient and trip the CB
        // SDK desync. Call viem's primitive directly on a chain-bound
        // client with assertChainId off. Default predicate (`status >= 200`)
        // covers both success and onchain failure; pollVerify surfaces
        // any reverts.
        setStatus('verifying')
        const statusClient = await getConnectorClient(wagmiConfig, {
          assertChainId: false,
          chainId: q.chain_id,
          account: address as `0x${string}`,
        })
        const final = await viemWaitForCallsStatus(statusClient, {
          id,
          timeout: 90_000,
        })
        const receipts = (final as { receipts?: Array<{ transactionHash?: string }> }).receipts || []
        const hash = receipts[0]?.transactionHash
        dbg('waitForCallsStatus:done', {
          id,
          finalStatus: (final as { status?: string }).status,
          statusCode: (final as { statusCode?: number }).statusCode,
          receiptCount: receipts.length,
          hash,
        })
        if (!hash) {
          dbgErr('waitForCallsStatus:no-hash', { id, final })
          throw new Error('Wallet completed payment but did not return a transaction hash. Refresh and check your wallet history before retrying — your funds may already be on the way.')
        }
        minedHash = hash
      } else if (isSafePath) {
        // ── Safe (multisig) path ──
        //
        // The Safe app is chain-scoped per deployment, so we skip the
        // `switchChain` step entirely — the Safe is already on whichever
        // chain the buyer opened it on. `eth_sendTransaction` /
        // `eth_writeContract` on a Safe returns an offchain
        // *safeTxHash*, not a real onchain hash; we poll Safe Tx
        // Service for the executed `transactionHash` and feed that to
        // pollVerify. Multi-sig Safes can take minutes-to-hours of
        // co-signer time — the "verifying" status stays up while
        // pollSafeTxService waits.
        dbg('safe:send:invoke', { chainId: q.chain_id, symbol: q.symbol })
        setStatus('signing-tx')
        const safeTxHash: string = q.symbol === 'ETH'
          ? await sendTransactionAsync({
              to: q.receive_address as `0x${string}`,
              value: BigInt(q.amount_raw),
              chainId: q.chain_id,
            })
          : await (async () => {
              if (!q.token_address) throw new Error('token_address missing')
              return writeContractAsync({
                address: q.token_address as `0x${string}`,
                abi: erc20Abi,
                functionName: 'transfer',
                args: [q.receive_address as `0x${string}`, BigInt(q.amount_raw)],
                chainId: q.chain_id,
              })
            })()
        dbg('safe:send:returned', { safeTxHash })
        setStatus('verifying')
        dbg('safe:tx:poll-start', { chainId: q.chain_id, safeTxHash })
        minedHash = await pollSafeTxService(q.chain_id, safeTxHash)
        dbg('safe:tx:poll-done', { safeTxHash, onChainHash: minedHash })
      } else {
        // ── Legacy path (EOA wallets, older WC sessions) ──
        //
        // Switch chain first; if the wallet refuses we surface an
        // actionable message ("approve all networks during handshake").
        // Then route the send through `sendWithRecovery` so wallets that
        // broadcast but don't return a hash via WC (Binance Wallet macOS,
        // intermittent Bitget / TokenPocket) don't strand the UI.
        if (walletChainId !== q.chain_id) {
          setStatus('switching')
          dbg('legacy:switchChain:invoke', { from: walletChainId, to: q.chain_id })
          try {
            await switchChainAsync({ chainId: q.chain_id })
            dbg('legacy:switchChain:done', { to: q.chain_id })
          } catch (switchErr) {
            dbgWarn('legacy:switchChain:failed', {
              from: walletChainId,
              to: q.chain_id,
              error: (switchErr as Error).message,
            })
            const isWc = connectionKind === 'walletConnect'
            const chainName = picked?.chain_name ?? `chain ${q.chain_id}`
            throw new Error(
              isWc
                ? `Your wallet refused to switch to ${chainName}. This usually means the WalletConnect session was approved for Ethereum only. Disconnect (button at the top), reconnect, and approve all networks listed in your wallet's prompt — then retry the payment.`
                : `Couldn't switch your wallet to ${chainName}. Please switch manually in your wallet and try again.`,
            )
          }
        }

        setStatus('signing-tx')

        // Capture the payer's pending-nonce BEFORE broadcast so the
        // nonce-based fallback in waitForReceiptOrReplacement works
        // even when our chain RPC never sees the original tx hash.
        let expectedNonce: number | undefined
        try {
          expectedNonce = await getTransactionCount(wagmiConfig, {
            address: address as `0x${string}`,
            blockTag: 'pending',
            chainId: q.chain_id,
          })
        } catch {
          // Best-effort — without this the helper falls back to its
          // own discovery path. Don't block on a transient RPC error.
        }

        const walletSend = q.symbol === 'ETH'
          ? () => sendTransactionAsync({
              to: q.receive_address as `0x${string}`,
              value: BigInt(q.amount_raw),
              chainId: q.chain_id,
            })
          : (() => {
              if (!q.token_address) throw new Error('token_address missing')
              const tokenAddress = q.token_address as `0x${string}`
              return () => writeContractAsync({
                address: tokenAddress,
                abi: erc20Abi,
                functionName: 'transfer',
                args: [q.receive_address as `0x${string}`, BigInt(q.amount_raw)],
                chainId: q.chain_id,
              })
            })()
        dbg('legacy:walletSend:invoke', {
          chainId: q.chain_id,
          symbol: q.symbol,
          expectedNonce,
        })
        const txHash: string = await sendWithRecovery({
          walletSend,
          payer: address as `0x${string}`,
          chainId: q.chain_id,
          expectedNonce,
        })
        dbg('legacy:walletSend:returned', { txHash })

        // Wait for the tx to actually be mined before telling the backend
        // to verify. Races viem's onReplaced-aware waitForTransactionReceipt
        // against a nonce-based watcher so speed-ups / replacements don't
        // strand the UI on the orphaned hash.
        minedHash = txHash
        try {
          const result = await waitForReceiptOrReplacement({
            wagmiConfig,
            chainId: q.chain_id,
            hash: txHash as `0x${string}`,
            payer: address as `0x${string}`,
            expectedNonce,
          })
          minedHash = result.hash
          dbg('legacy:receipt:done', {
            original: txHash,
            mined: minedHash,
            replaced: minedHash !== txHash,
            cancelled: result.cancelled,
          })
          if (result.cancelled) {
            throw new Error(`Transaction was cancelled ${walletLocationPhrase(connectionKind, connectedWalletName)} — please retry.`)
          }
        } catch (e) {
          const msg = (e as Error).message ?? ''
          if (msg.startsWith('Transaction was cancelled')) throw e
          dbgWarn('legacy:receipt:fallback', { txHash, error: msg })
          // Otherwise indexer lag / network blip — pollVerify's retry
          // loop picks it up; we keep `minedHash = txHash` since we
          // weren't able to detect a replacement.
        }
      }

      // Step 7: Verify
      // Persist the broadcast tx BEFORE verifying so a reload during the
      // verify wait recovers into verify-only mode (never a fresh Pay).
      persistTx(q, minedHash)
      setPendingTxHash(minedHash)
      setStatus('verifying')
      dbg('verify:start', { minedHash, chainId: q.chain_id })
      await pollVerify(q, minedHash)
      dbg('verify:done', { minedHash })
      // Verified — safe to drop the recovery record.
      clearPersistedTx()
      // Render the inline success card and start the redirect. We still
      // call `onConfirmed` so the parent can observe completion (today it's
      // unused; kept for future hooks). The actual redirect runs from this
      // component's success-status effect so the visual transition stays in
      // the same `wc-root` frame — no swap to a separate SuccessStep view.
      setConfirmedTxHash(minedHash)
      setStatus('success')
      onConfirmed(minedHash, q)
    } catch (e: unknown) {
      const err = e as { shortMessage?: string; message?: string; name?: string }
      dbgErr('handlePay:caught', {
        name: err.name,
        message: err.message,
        shortMessage: err.shortMessage,
      })
      setError(err.shortMessage || err.message || String(e))
      setStatus('error')
    }
  }

  // ── Verify-only recovery ──
  // Re-runs verification of an ALREADY-broadcast tx without touching the
  // wallet — no re-sign, no re-send, no new on-chain tx. This is the safe
  // recovery path whenever we hold a broadcast hash (after a verify
  // rate-limit, a timeout, or a reload). It's deliberately separate from
  // handlePay so a paid buyer can never be funneled back into paying again.
  async function runVerifyOnly(q: Quote, hash: string) {
    setError(null)
    setQuote(q)
    setPendingTxHash(hash)
    setStatus('verifying')
    dbg('verify-only:start', { hash, chainId: q.chain_id })
    try {
      await pollVerify(q, hash)
      clearPersistedTx()
      setConfirmedTxHash(hash)
      setStatus('success')
      onConfirmed(hash, q)
    } catch (e) {
      const err = e as { shortMessage?: string; message?: string }
      dbgErr('verify-only:caught', { message: err.message })
      setError(err.shortMessage || err.message || String(e))
      setStatus('error')
    }
  }

  // Bound to the "Check payment status" button shown in the error state
  // when a tx was already broadcast (see button render below).
  function retryVerifyOnly() {
    if (!quote || !pendingTxHash) return
    runVerifyOnly(quote, pendingTxHash)
  }

  // Mount recovery: if a broadcast tx for this order is persisted (tab
  // reload / crash mid-verify), resume verification of that exact tx
  // rather than letting the buyer restart payment. Runs once.
  const recoveredTxRef = useRef(false)
  useEffect(() => {
    if (recoveredTxRef.current) return
    recoveredTxRef.current = true
    try {
      const raw = window.sessionStorage.getItem(txStorageKey)
      if (!raw) return
      const saved = JSON.parse(raw) as { txHash?: string; quote?: Quote }
      if (saved?.txHash && saved?.quote) {
        dbg('verify-only:recovered-from-storage', { hash: saved.txHash })
        runVerifyOnly(saved.quote, saved.txHash)
      }
    } catch {
      // malformed / storage unavailable — ignore, normal flow proceeds
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Build the "Pay: 0.000004 ETH on Arbitrum" label dynamically from the
  // currently-picked option. Pre-quote we use:
  //   USDC/USDT0 \u2192 totalUsd \u00d7 10^6 (1:1 USD-pegged stables)
  //   ETH \u2192 totalUsd / ethPriceUsd (live dual-oracle from /payment-options/)
  // The quote-creation endpoint locks in the exact amount on its side, so
  // the displayed value matches what the wallet will actually be asked to
  // sign within ~0.5% (covered by the verify-side slippage tolerance).
  function idlePayLabel(): string {
    if (!picked) return 'Pay now'
    const raw = expectedRaw(picked.symbol)
    if (raw === null) return `Pay with ${picked.symbol} on ${picked.chain_name}`
    const decimals = picked.symbol === 'ETH' ? 18 : 6
    return `Pay: ${formatBalance(raw.toString(), decimals)} ${picked.symbol} on ${picked.chain_name}`
  }

  const where = walletLocationPhrase(connectionKind, connectedWalletName)
  const buttonLabel = (() => {
    switch (status) {
      case 'idle': return idlePayLabel()
      case 'challenge': return 'Preparing\u2026'
      case 'signing-challenge': return `Sign message ${where}\u2026`
      case 'quoting': return 'Creating quote\u2026'
      case 'switching': return 'Switching chain\u2026'
      case 'signing-tx': return `Confirm payment ${where}\u2026`
      case 'verifying':
        // During a rate-limit cooldown, show the countdown so the buyer
        // knows we're waiting deliberately (not stuck) \u2014 and crucially the
        // tx is already paid, we're only re-checking it.
        if (cooldownRemaining > 0) {
          return `Network busy \u2014 retrying in ${cooldownRemaining}s\u2026`
        }
        // Friendly copy, no bare "0/1" \u2014 that fraction reads as a stalled
        // counter to non-technical buyers. Show plain "Confirming\u2026" while
        // we're at zero confirmations, and only surface a progress count
        // once we have \u2265 1 of the required blocks AND the chain actually
        // requires more than one block (meaningful on Ethereum L1 with 3
        // confs; never shown for L2s with 1 conf required).
        if (confirmProgress && confirmProgress.current > 0 && confirmProgress.required > 1) {
          return `Confirming \u00b7 ${confirmProgress.current} of ${confirmProgress.required} blocks`
        }
        return 'Confirming onchain\u2026'
      case 'success': return ''
      case 'error': return 'Retry'
    }
  })()

  const busy = status !== 'idle' && status !== 'error'

  // On success, schedule the redirect to the order page. The success
  // card lingers for 2 s before navigating so the buyer has time to
  // (a) register the green check + "Payment confirmed" copy as the
  // emotional end-of-flow beat, (b) read or click the explorer link
  // before being whisked away, and (c) on slower wallets / Coinbase
  // popups, gives any wallet-side UI time to finish closing before
  // the page navigates. We keep the buyer in CheckoutStep's frame
  // (WalletHeader + same `wc-root` wrapper) throughout \u2014 only the
  // status card swaps from verifying \u2192 success.
  useEffect(() => {
    if (status !== 'success') return
    const fe = (config.frontendOrderUrlTemplate || '').trim()
    let target: string | null = null
    if (fe) {
      target = fe
        .replace(/\{code\}/g, encodeURIComponent(config.orderCode))
        .replace(/\{secret\}/g, encodeURIComponent(config.orderSecret))
    } else if (config.pretixOrderUrl) {
      target = config.pretixOrderUrl
    }
    const t = setTimeout(() => {
      if (target) window.location.href = target
      else window.location.reload()
    }, 2000)
    return () => clearTimeout(t)
  }, [status, config.frontendOrderUrlTemplate, config.orderCode, config.orderSecret])

  // Sufficiency check for the currently picked option — drives the Pay
  // button's disabled state. Null when we can't tell yet (balances
  // still loading or chain RPC unavailable); only `false` blocks the
  // button so we don't grey out Pay during the first-render race.
  const pickedSufficient: boolean | null = (() => {
    if (!picked) return null
    const entry = findBalance(balancesQuery.data, picked.chain_id, picked.symbol)
    const expected = expectedRaw(picked.symbol)
    if (!entry || expected === null) return null
    try {
      return BigInt(entry.balance) >= expected
    } catch {
      return null
    }
  })()
  const pickedInsufficient = pickedSufficient === false

  // Mobile-Safari CB SW warning + deep-link to the CB Wallet in-app
  // browser (Pretix URL carries order_code/order_secret so it resumes).
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent || '' : ''
  const showCbMobileWarning = /iPhone|iPad|iPod|Android/i.test(ua) && !/Coinbase/i.test(ua) && connectionKind === 'coinbaseWallet'
  const cbDappUrl = typeof window !== 'undefined'
    ? `https://go.cb-w.com/dapp?cb_url=${encodeURIComponent(window.location.href)}`
    : ''

  // Single status-card rendering for every non-idle state: signing chain,
  // verifying, success, error. Picks tone + icon + title from `status`,
  // shows amount + tx-link rows when a quote/hash exist. Replaces the
  // picker section in the main return while WalletHeader + the
  // `wc-root` wrapper stay constant — so the buyer never sees a layout
  // context swap from picking → paying → confirmed.
  const statusCardState: 'pending' | 'success' | 'error' | null =
    status === 'success' ? 'success'
    : status === 'error' ? 'error'
    : status !== 'idle' ? 'pending'
    : null

  const statusCardTitle = (() => {
    switch (status) {
      case 'challenge':         return 'Preparing payment…'
      case 'signing-challenge': return `Sign in your wallet ${where}…`
      case 'quoting':           return 'Creating quote…'
      case 'switching':         return `Switch network ${where}…`
      case 'signing-tx':        return `Confirm payment ${where}…`
      case 'verifying':
        if (cooldownRemaining > 0) {
          return `Network busy — retrying in ${cooldownRemaining}s`
        }
        // See `buttonLabel` for rationale — skip the fraction when we're
        // at 0 or the chain only needs a single block (avoids the noisy
        // "0/1" reading), and frame the progress in natural language
        // when the fraction IS meaningful.
        if (confirmProgress && confirmProgress.current > 0 && confirmProgress.required > 1) {
          return `Confirming · ${confirmProgress.current} of ${confirmProgress.required} blocks`
        }
        return 'Confirming onchain…'
      case 'success':           return 'Payment confirmed'
      case 'error':
        // Distinguish "user rejected in wallet" from actual failures.
        // A wallet rejection is the buyer changing their mind, not a
        // failure — calling it "Payment failed" reads as alarmist.
        // Most wallets surface rejection with these phrases in
        // shortMessage/message.
        if (error && /(user (?:rejected|denied|cancel))|^rejected|user closed/i.test(error)) {
          return 'Payment cancelled'
        }
        return "Couldn't complete payment"
      default:                  return ''
    }
  })()

  // One-line context shown directly under the title. The signing-challenge
  // state is the most confusing one — buyers see "Sign in your wallet" and
  // reasonably wonder whether they're committing to a transaction (gas?
  // is this the payment?). Explicit "free, offchain, no gas" reassurance
  // there. For other states we keep the description short or omit when
  // the title alone is clear (challenge / quoting are quick, self-evident
  // prep steps).
  const statusCardDescription = (() => {
    switch (status) {
      case 'signing-challenge':
        return 'Free offchain signature — no gas fee'
      case 'switching':
        return 'Approve the network change — no gas fee'
      case 'signing-tx':
        return 'This is the onchain payment'
      case 'verifying':
        if (cooldownRemaining > 0) {
          // Reassure: their payment is already on-chain; we're just waiting
          // out a busy-network throttle before re-checking it. No re-pay.
          return 'Your payment is sent — waiting to re-check it. No need to pay again.'
        }
        // Ethereum L1's ~12 s block time means a single confirmation is
        // ~12 s; the default 3-conf setup is ~36 s — long enough buyers
        // wonder if it's stuck. Surface the per-block expectation only
        // when more than one block is actually required (mainnet's
        // default). If the operator has configured 1 confirmation, drop
        // "per block" since the phrase is meaningless for a single-block
        // wait. L2s (Arbitrum, Optimism, Base, Polygon) confirm in
        // seconds and skip the hint entirely.
        if (quote?.chain_id === 1) {
          const multiBlock = !confirmProgress || confirmProgress.required > 1
          return multiBlock
            ? 'Waiting for the network to confirm (~12 s per block)'
            : 'Waiting for the network to confirm (~12 s)'
        }
        return 'Waiting for the network to confirm'
      default:
        return null
    }
  })()

  // Resolve the tx hash for the status card's Transaction row. During
  // verifying we use `pendingTxHash` (set the moment the wallet returns
  // the hash); on success we prefer `confirmedTxHash` which is identical
  // in practice but explicit. Either may be null if we never got past
  // signing — the row then shows "Waiting for transaction…".
  const statusCardTxHash = confirmedTxHash || pendingTxHash
  const statusCardExplorerBase = quote && chainMetadata[String(quote.chain_id)]?.explorer_url
  const statusCardTxUrl = statusCardTxHash && statusCardExplorerBase
    ? `${statusCardExplorerBase}${statusCardTxHash}`
    : null

  // Picker + retry control are shown during idle (initial choice) AND
  // error (retry path). The status card sits above and surfaces the
  // failure context; the picker below lets the buyer either retry the
  // same option or switch tokens/networks and try again. Pay button
  // label flips to "Retry" automatically (see buttonLabel switch).
  const showPicker = status === 'idle' || status === 'error'
  // True when we're in the error state but a tx was already broadcast.
  // In this case the recovery action must be verify-only — re-paying
  // would double-charge the buyer — so the primary button re-verifies
  // the existing hash instead of calling handlePay.
  const hasBroadcastTx = status === 'error' && !!pendingTxHash && !!quote

  return (
    <div className="wc-root">
      <WalletHeader disabled={busy} />

      {isSafePath && (
        <div className="wc-safe-notice" role="status">
          <strong>Safe detected — payment is experimental.</strong> Keep
          this tab open while the transaction is signed and executed.
          {safeThreshold !== null && safeThreshold > 1 && (
            <>
              {' '}
              For Safes with multiple signers, use a <strong>dedicated
              browser</strong> for the Safe app where co-signers add
              signatures — this prevents losing the WalletConnect
              connection to your Safe mid-flow.
            </>
          )}
        </div>
      )}

      {/* Unified status card — drives the visual for every state except
          'idle'. Same layout, same Transaction row visual, same tx-link
          styling for signing → verifying → success → error. The picker
          (asset chips, network list, Pay button) below is gated on
          status==='idle' so it hides when this card takes over. */}
      {statusCardState && (
        <div className="wc-status-card" data-state={statusCardState}>
          <div className="wc-status-card-icon" aria-hidden="true">
            {statusCardState === 'success' ? '✓' : statusCardState === 'error' ? '!' : ''}
          </div>
          <h3 className="wc-status-card-title">{statusCardTitle}</h3>
          {statusCardDescription && (
            <p className="wc-status-card-description">{statusCardDescription}</p>
          )}
          {quote && (
            <div className="wc-status-card-info">
              <div className="wc-status-card-row">
                <span className="wc-status-card-label">Amount</span>
                <span className="wc-status-card-value">
                  {formatAmount(quote)} on {chainMetadata[String(quote.chain_id)]?.name || `chain ${quote.chain_id}`}
                </span>
              </div>
              <div className="wc-status-card-row">
                <span className="wc-status-card-label">Transaction</span>
                <span className="wc-status-card-value">
                  {statusCardTxUrl ? (
                    <a href={statusCardTxUrl} target="_blank" rel="noopener noreferrer">
                      View on explorer →
                    </a>
                  ) : (
                    <span className="wc-status-card-pending">Waiting for transaction…</span>
                  )}
                </span>
              </div>
            </div>
          )}
          {statusCardState === 'success' && (
            <p className="wc-status-card-message">Taking you to your order…</p>
          )}
          {statusCardState === 'error' && error && (
            <p className="wc-status-card-message wc-status-card-message--error">{error}</p>
          )}
        </div>
      )}

      {showPicker && (
        <h3 style={{ marginTop: 0 }}>
          {/* Header reflects the option count, not the error state — the
              Pay button label already swaps to "Retry" on error, so the
              header doesn't need to also shout "Try again". Single option
              reads as "Confirm payment" (nothing to pick), multi-option
              keeps the original "Select payment method". */}
          {options.length === 1 ? 'Confirm payment' : 'Select payment method'}
        </h3>
      )}

      {/* DEBUG panel — only rendered when a dev has flipped the toggle
          by typing `wcDebug()` in the browser console. Lets QA force
          the tx-hash recovery wrapper down a specific path without
          rebuilding. Type `wcDebug()` again to hide. */}
      {debugEnabled && (
        <div className="wc-debug-panel">
          <div className="wc-debug-label">DEBUG · simulate tx-hash recovery</div>
          <div className="wc-debug-options">
            {([
              ['normal', 'Normal (wallet returns hash)'],
              ['no-hash', 'No hash → discovery should win'],
              ['no-hash-no-discovery', 'No hash + no discovery → manual entry'],
            ] as Array<['normal' | 'no-hash' | 'no-hash-no-discovery', string]>).map(([value, label]) => (
              <label key={value} className="wc-debug-option">
                <input
                  type="radio"
                  name="wc-debug-simulate"
                  value={value}
                  checked={simulateMode === value}
                  onChange={() => setSimulateMode(value)}
                  disabled={busy}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          {/* Rate-limit toggle. Safe to flip mid-verify (ref-backed) — turn
              on to watch the backoff hold the buyer in "verifying" with no
              re-pay button, turn off to see verification recover. */}
          <label className="wc-debug-option" style={{ marginTop: 8 }}>
            <input
              type="checkbox"
              checked={simulateRateLimit}
              onChange={(e) => setSimRateLimit(e.target.checked)}
            />
            <span>Simulate rate limit on verify (429)</span>
          </label>
        </div>
      )}

      {showPicker && !ethAvailable && ethDisabledReason && (
        <div className="wc-notice">
          {ethReasonText(
            ethDisabledReason,
            // Stables actually offered by this event (= options minus ETH).
            // Keeps the suggestion in sync with the plugin's chain/token toggles.
            [...new Set(options.filter(o => o.symbol !== 'ETH').map(o => o.symbol))],
          )}
        </div>
      )}

      {showPicker && options.length === 0 && (
        <div className="wc-error">No payment options available.</div>
      )}

      {/* Step 1: Token selection chips */}
      {showPicker && (() => {
        // Canonical display order for the asset chips — independent of the
        // order the backend returns options in. Symbols not in this list
        // fall to the end, keeping the picker stable if new tokens are added.
        const ASSET_ORDER = ['ETH', 'USDC', 'USDT0']
        const uniqueSymbols = [...new Set(options.map(o => o.symbol))].sort((a, b) => {
          const ia = ASSET_ORDER.indexOf(a)
          const ib = ASSET_ORDER.indexOf(b)
          if (ia === -1 && ib === -1) return a.localeCompare(b)
          if (ia === -1) return 1
          if (ib === -1) return -1
          return ia - ib
        })
        const networksForToken = tokenFilter
          ? options.filter(o => o.symbol === tokenFilter)
          : []

        return (
          <>
            <div className="wc-asset-selection">
              <span className="wc-asset-label">Asset</span>
              <div className="wc-asset-chips">
                {uniqueSymbols.map(sym => (
                  <button
                    key={sym}
                    type="button"
                    className={`wc-asset-chip ${tokenFilter === sym ? 'wc-asset-chip--active' : ''}`}
                    disabled={busy}
                    onClick={() => {
                      setTokenFilter(sym)
                      // Auto-select first network for this token
                      const first = options.find(o => o.symbol === sym)
                      if (first) pickAndMaybeSwitch(first)
                    }}
                  >
                    {TOKEN_LOGOS[sym] && (
                      <img src={TOKEN_LOGOS[sym]} alt="" className="wc-asset-icon" aria-hidden="true" />
                    )}
                    <span>{sym}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2: Network selection rows */}
            {tokenFilter && networksForToken.length > 0 && (
              <div className="wc-network-selection">
                <div className="wc-network-header">
                  <span className="wc-network-label">Network</span>
                  {/* Mirror the x402 storefront's "Refresh balances" affordance.
                       Wallet balances move when the buyer sends/receives between
                       the page load and selecting a network — without a manual
                       refresh, an insufficient row can stay greyed out for the
                       full 60s React Query refetchInterval. */}
                  <button
                    type="button"
                    className={
                      'wc-network-refresh' +
                      (balancesQuery.isFetching ? ' wc-network-refresh--loading' : '')
                    }
                    onClick={() => balancesQuery.refetch()}
                    disabled={balancesQuery.isFetching || busy}
                    aria-label="Refresh balances"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                         strokeLinejoin="round" aria-hidden="true">
                      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                      <path d="M21 3v5h-5" />
                      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                      <path d="M3 21v-5h5" />
                    </svg>
                    <span>Refresh</span>
                  </button>
                </div>
                <div className="wc-network-list">
                  {networksForToken.map(opt => {
                    const isSelected = picked?.chain_id === opt.chain_id && picked?.symbol === opt.symbol
                    const logo = NETWORK_LOGOS[opt.chain_id]
                    const balanceEntry = findBalance(balancesQuery.data, opt.chain_id, opt.symbol)
                    const expected = expectedRaw(opt.symbol)
                    let sufficient: boolean | null = null
                    if (balanceEntry && expected !== null) {
                      try {
                        sufficient = BigInt(balanceEntry.balance) >= expected
                      } catch {
                        sufficient = null
                      }
                    }
                    // Balance line mirrors the x402 storefront format:
                    //   "Balance: 0.00332616 ETH / $7.63"
                    // ETH USD is computed off `ethPriceUsd` from payment-options;
                    // stablecoins (USDC/USDT/USDT0/DAI) are 1:1 with USD so the
                    // formatted balance IS the dollar figure.
                    let balanceDisplay: string | null = null
                    if (balanceEntry) {
                      const formatted = formatBalance(balanceEntry.balance, balanceEntry.decimals)
                      let usd: string | null = null
                      if (opt.symbol === 'ETH' && ethPriceUsd) {
                        const eth = Number(balanceEntry.balance) / 10 ** balanceEntry.decimals
                        usd = (eth * ethPriceUsd).toFixed(2)
                      } else if (opt.symbol !== 'ETH') {
                        // Stablecoin — formatted balance = USD value (1:1).
                        const numeric = Number(formatted.replace(/,/g, ''))
                        if (Number.isFinite(numeric)) usd = numeric.toFixed(2)
                      }
                      balanceDisplay = usd != null
                        ? `Balance: ${formatted} ${opt.symbol} / $${usd}`
                        : `Balance: ${formatted} ${opt.symbol}`
                    }
                    const insufficient = sufficient === false
                    return (
                      <button
                        key={`${opt.chain_id}-${opt.symbol}`}
                        type="button"
                        className={`wc-network-row ${isSelected ? 'wc-network-row--selected' : ''} ${insufficient ? 'wc-network-row--insufficient' : ''}`}
                        // Allow selecting an insufficient row anyway — the
                        // ETH check is heuristic ($3000/ETH ceiling) and the
                        // real sufficiency check happens at quote time. This
                        // prevents over-blocking when the heuristic is wrong.
                        disabled={busy}
                        onClick={() => pickAndMaybeSwitch(opt)}
                      >
                        <span className="wc-network-row-left">
                          {logo && (
                            <img src={logo} alt="" className="wc-network-icon" aria-hidden="true" />
                          )}
                          <span className="wc-network-row-name">{opt.chain_name}</span>
                        </span>
                        <span className="wc-network-row-right">
                          {balanceDisplay && (
                            <span
                              className={`wc-network-row-balance ${insufficient ? 'wc-network-row-balance--low' : ''}`}
                              title={
                                insufficient
                                  ? 'Balance may be insufficient — final check happens at quote time'
                                  : undefined
                              }
                            >
                              {balanceDisplay}
                            </span>
                          )}
                          {balancesQuery.isLoading && !balanceDisplay && (
                            <span className="wc-network-row-balance">…</span>
                          )}
                          {isSelected && <span className="wc-network-row-check">&#10003;</span>}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </>
        )
      })()}

      {/* Pre-pay summary line — shown only in idle state so the buyer
          sees what they're about to send. Once they click Pay, the
          unified status card above takes over and surfaces amount + tx
          link in its own rows. The recipient `<code>` is dropped from
          the card-driven views since the hash is the more relevant
          artifact once a transaction is in flight. */}
      {status === 'idle' && quote && (
        <p className="wc-small" style={{ marginTop: 8 }}>
          Amount: <strong>{formatAmount(quote)}</strong> to{' '}
          <code style={{ wordBreak: 'break-all' }}>{quote.receive_address}</code>
        </p>
      )}

      {/* Pay (or Retry) button — visible during idle AND error so the
          buyer has a clear retry path on failure. Hidden during in-flight
          + success states (the status card owns the in-flight UI; success
          auto-redirects). Also defensively gated on `address` for the
          brief window between a disconnect event firing and WCPaymentApp's
          stage transition. */}
      {showPicker && address && (showCbMobileWarning ? (
        <div className="wc-cb-mobile-warning" role="alert">
          <p>
            <strong>Heads-up:</strong> for the smoothest Coinbase / Base
            Smart Wallet checkout on mobile, continue inside the Coinbase
            Wallet app:
          </p>
          <a className="wc-cb-mobile-warning-link" href={cbDappUrl}>
            Continue in Coinbase Wallet →
          </a>
        </div>
      ) : (
        hasBroadcastTx ? (
          // Safe recovery: re-verify the already-broadcast tx. Never
          // re-enters handlePay, so a paid buyer can't be charged twice.
          <button
            type="button"
            className="btn btn-primary btn-lg btn-block wc-pay-btn"
            disabled={busy}
            onClick={retryVerifyOnly}
          >
            Check payment status
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary btn-lg btn-block wc-pay-btn"
            disabled={!picked || busy || pickedInsufficient}
            onClick={handlePay}
            title={pickedInsufficient ? `Insufficient ${picked?.symbol ?? 'token'} balance on ${picked?.chain_name ?? 'this network'}` : undefined}
          >
            {pickedInsufficient ? `Insufficient ${displaySymbol(picked?.symbol ?? '')} balance` : buttonLabel}
          </button>
        )
      ))}

      {/* Helper link when ETH balance is insufficient on the picked option.
          Same subtle styling as the ConnectStep "where to get a wallet" link
          so the visual vocabulary stays consistent. Only shown for ETH
          since the destination URL is ETH-specific — for stables the buyer
          typically already knows where to top up. */}
      {showPicker && pickedInsufficient && picked?.symbol === 'ETH' && (
        <a
          className="wc-find-wallet wc-insufficient-helper"
          href="https://ethereum.org/get-eth/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Where to get ETH? →
        </a>
      )}

      {/* Status banner for the recovery flow. Sits between the Pay button
          and the error area so the buyer sees it the moment discovery
          starts polling, and again when the manual entry surfaces. */}
      {recoveryStatus === 'discovery' && (
        <div className="wc-recovery-banner">
          Looking for your transaction on chain — please do not close this window…
        </div>
      )}

      {/* Manual hash escape hatch — appears after the auto window expires
          without finding the tx via nonce-discovery. Buyer pastes the hash
          from their wallet's history; we validate it onchain (correct
          payer + nonce) before accepting. */}
      {recoveryStatus === 'manual' && (
        <div className="wc-recovery-prompt">
          <div className="wc-recovery-message">
            We can’t tell whether your wallet sent the transaction. If your
            wallet shows a successful payment, paste the transaction hash
            here so we can verify it.
          </div>
          <div className="wc-recovery-row">
            <input
              type="text"
              value={manualHashInput}
              onChange={(e) => setManualHashInput(e.target.value)}
              placeholder="0x…"
              disabled={manualHashSubmitting}
              spellCheck={false}
              autoComplete="off"
              className="wc-recovery-input"
            />
            <button
              type="button"
              className="btn btn-primary wc-recovery-submit"
              onClick={submitManualHash}
              disabled={manualHashSubmitting || !manualHashInput.trim()}
            >
              {manualHashSubmitting ? 'Verifying payment…' : 'Verify payment'}
            </button>
          </div>
          {manualHashError && <div className="wc-recovery-error">{manualHashError}</div>}
        </div>
      )}

      {/* Error copy is shown inside the status card's `.wc-status-card-message--error`
          slot now — no separate `.wc-error` strip below the card. The
          support-pill link is still rendered after this so a stuck buyer
          has a help path. */}

      {/* Support fallback. Self-serve manual verification was removed because
          it required an in-memory quote that expires with the browser session,
          so in the realistic failure modes (tab crash, network timeout) it
          couldn't actually recover and risked double-payment. Stuck buyers
          now route through support; admins can manually verify from the
          admin page using the confirmed tx hash. */}
      {status === 'error' && (() => {
        // Build a best-effort support-email body. Everything we know from the
        // current session gets pre-filled so the operator can triage quickly;
        // the transaction hash is left blank for the buyer to paste in.
        // Always emit every field so the operator has a consistent template
        // to work with — any value we don't have becomes a placeholder the
        // buyer can fill in from their wallet history.
        const networkValue = quote ? (chainMetadata[String(quote.chain_id)]?.name || String(quote.chain_id)) : ''
        const tokenValue = quote ? quote.symbol : ''
        const amountValue = quote ? formatAmount(quote) : ''
        const recipientValue = quote ? quote.receive_address : ''
        const fill = (v: string) => v || '(please fill in)'
        const lines: string[] = [
          "Hi,",
          "",
          "I tried to pay for a Pretix order with crypto and the page didn't complete.",
          "",
          `Email: ${fill(config.buyerEmail || '')}`,
          `Order code: ${config.orderCode}`,
          `Wallet: ${fill(connectedWalletName || '')}`,
          `Connection: ${connectionTypeLabel(connectionKind)}`,
          `Wallet address: ${fill(address || '')}`,
          `Network: ${fill(networkValue)}`,
          `Token: ${fill(tokenValue)}`,
          `Amount sent: ${fill(amountValue)}`,
          `Recipient: ${fill(recipientValue)}`,
          `Transaction hash: (paste the 0x\u2026 hash from your wallet here)`,
          // Include the last in-page error string when present so the
          // operator has the exact failure context the buyer saw \u2014 no
          // need to ask "what error did you get?" in a follow-up.
          ...(error ? ['', `Error: ${error}`] : []),
          "",
          "Thanks!",
        ]
        const errSubject = `Payment issue for order ${config.orderCode}`
        const errBody = lines.join('\n')
        const mailtoHref = config.supportEmail
          ? `mailto:${config.supportEmail}?subject=${encodeURIComponent(errSubject)}&body=${encodeURIComponent(errBody)}`
          : null
        return (
          <div className="wc-support-block" style={{ marginTop: 16, padding: 12, background: '#f7f5ff', borderRadius: 8 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Already sent the transaction?</div>
            <div style={{ fontSize: 14, lineHeight: 1.4 }}>
              <strong>Don't re-send</strong> — you'd be charged twice.
              {' '}
              {mailtoHref ? (
                <>
                  <a
                    href={mailtoHref}
                    onClick={() => setSupportPopup({ subject: errSubject, body: errBody, mailto: mailtoHref })}
                  >Email the event organizer</a> — we've pre-filled everything we know; just add your transaction hash and send.
                </>
              ) : (
                <>Contact the event organizer with your order code <code>{config.orderCode}</code>, the transaction hash, and the wallet address you paid from.</>
              )}
            </div>
          </div>
        )
      })()}

      {/* Persistent support link. Always rendered when an operator-side
          support email is configured — visible during the picker, while
          confirming, and after errors — so a stuck buyer can always reach
          out. The pre-fill includes every piece of session context we have
          so the operator can triage with one read. The error-state recovery
          block above is more specific (handles "I already sent the tx");
          this is the catch-all. */}
      {config.supportEmail && (() => {
        const networkValue = picked ? picked.chain_name : (quote ? (chainMetadata[String(quote.chain_id)]?.name || String(quote.chain_id)) : '')
        const tokenValue = picked ? picked.symbol : (quote ? quote.symbol : '')
        const amountValue = quote ? formatAmount(quote) : ''
        const recipientValue = quote ? quote.receive_address : ''
        const fill = (v: string) => v || '(please fill in)'
        const lines: string[] = [
          'Hi,',
          '',
          'I need help with my Devcon ticket payment.',
          '',
          `Email: ${fill(config.buyerEmail || '')}`,
          `Order code: ${config.orderCode}`,
          `Wallet: ${fill(connectedWalletName || '')}`,
          `Connection: ${connectionTypeLabel(connectionKind)}`,
          `Wallet address: ${fill(address || '')}`,
          `Network: ${fill(networkValue)}`,
          `Token: ${fill(tokenValue)}`,
          `Amount: ${fill(amountValue)}`,
          `Recipient: ${fill(recipientValue)}`,
          `Stage: ${status}`,
          ...(error ? [`Error: ${error}`] : []),
          '',
          'What I need help with: (please describe)',
          '',
          'Thanks!',
        ]
        const subject = `Payment help for order ${config.orderCode}`
        const body = lines.join('\n')
        const mailtoHref = `mailto:${config.supportEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
        return (
          <div className="wc-support-pill">
            <p>
              Need help?{' '}
              <a
                href={mailtoHref}
                onClick={() => setSupportPopup({ subject, body, mailto: mailtoHref })}
              >
                <strong>Contact support</strong>
              </a>
            </p>
          </div>
        )
      })()}
      {supportPopup && config.supportEmail && (
        <SupportCopyPopup
          subject={supportPopup.subject}
          body={supportPopup.body}
          mailto={supportPopup.mailto}
          supportEmail={config.supportEmail}
          onClose={() => setSupportPopup(null)}
        />
      )}
    </div>
  )
}

// Popup that mirrors the contact-support mailto in copy-pasteable form.
// Opens alongside the buyer's mail client when they click any "Contact
// support" / "Email the event organizer" link — useful when their mail
// client doesn't auto-fill mailto links (corporate networks, browsers
// with no default handler, or when the body is long enough that the
// mailto URL gets truncated).
function SupportCopyPopup({
  subject,
  body,
  mailto,
  supportEmail,
  onClose,
}: {
  subject: string
  body: string
  mailto: string
  supportEmail: string
  onClose: () => void
}) {
  const [copiedField, setCopiedField] = useState<'subject' | 'body' | 'email' | null>(null)
  const copy = async (text: string, field: 'subject' | 'body' | 'email') => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 1500)
    } catch {
      // older browsers / insecure contexts: silently no-op.
    }
  }
  const field = (label: string, value: string, key: 'subject' | 'body' | 'email', multiline?: boolean) => (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          {label}
        </span>
        <button
          type="button"
          onClick={() => copy(value, key)}
          style={{
            padding: '2px 10px', fontSize: 12, fontWeight: 600,
            background: copiedField === key ? '#1a7f37' : '#f3f3f3',
            color: copiedField === key ? '#fff' : '#333',
            border: '1px solid ' + (copiedField === key ? '#1a7f37' : '#ccc'),
            borderRadius: 4, cursor: 'pointer',
          }}
        >
          {copiedField === key ? 'Copied!' : 'Copy'}
        </button>
      </div>
      {multiline ? (
        <textarea
          readOnly
          value={value}
          rows={Math.min(14, Math.max(6, value.split('\n').length))}
          style={{
            width: '100%', padding: 10, fontFamily: 'ui-monospace, monospace',
            fontSize: 12.5, lineHeight: 1.5, border: '1px solid #ddd',
            borderRadius: 6, resize: 'vertical', boxSizing: 'border-box',
          }}
          onFocus={e => e.currentTarget.select()}
        />
      ) : (
        <input
          readOnly
          value={value}
          style={{
            width: '100%', padding: '8px 10px', fontFamily: 'ui-monospace, monospace',
            fontSize: 13, border: '1px solid #ddd', borderRadius: 6, boxSizing: 'border-box',
          }}
          onFocus={e => e.currentTarget.select()}
        />
      )}
    </div>
  )
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 10000, padding: 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#fff', borderRadius: 12, padding: 20,
          maxWidth: 640, width: '100%', maxHeight: '90vh', overflow: 'auto',
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Contact support</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              padding: 4, fontSize: 20, lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
        <p style={{ fontSize: 14, color: '#555', margin: '0 0 16px' }}>
          Your mail client should open automatically. If it doesn&apos;t, copy the fields
          below and send them to <strong>{supportEmail}</strong>.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {field('To', supportEmail, 'email')}
          {field('Subject', subject, 'subject')}
          {field('Message', body, 'body', true)}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '8px 16px', border: '1px solid #ccc', background: '#fff',
              borderRadius: 6, cursor: 'pointer', fontSize: 14,
            }}
          >
            Close
          </button>
          <a
            href={mailto}
            style={{
              padding: '8px 16px', background: '#000', color: '#fff',
              borderRadius: 6, textDecoration: 'none', fontSize: 14, fontWeight: 600,
            }}
          >
            Open in mail app
          </a>
        </div>
      </div>
    </div>
  )
}
