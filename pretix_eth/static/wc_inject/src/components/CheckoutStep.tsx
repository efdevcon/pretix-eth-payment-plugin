import { useState, useEffect, useRef } from 'react'
import {
  useAccount,
  useSignMessage,
  useSwitchChain,
  useWriteContract,
  useSendTransaction,
  useConfig,
} from 'wagmi'
import { useWalletInfo } from '@reown/appkit/react'
import { classifyConnection, walletLocationPhrase } from '../walletConnection'
import {
  waitForTransactionReceipt,
  getTransaction,
  getTransactionCount,
  getBlock,
  getBlockNumber,
} from 'wagmi/actions'
import { erc20Abi } from 'viem'
import { NETWORK_LOGOS, TOKEN_LOGOS } from '../assetIcons'
import type { WCConfig } from '../config'
import type { PaymentOption } from '../hooks/usePaymentOptions'
import type { Quote } from '../WCPaymentApp'
import { useWalletBalances, findBalance, formatBalance } from '../hooks/useWalletBalances'
import { WalletHeader } from './WalletHeader'

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
  | 'error'

function parseOrgAndEvent(): { organizer: string; event: string } {
  const match = window.location.pathname.match(/^\/([^/]+)\/([^/]+)/)
  if (!match) throw new Error('Could not parse organizer/event from URL')
  return { organizer: match[1], event: match[2] }
}

/** Format a raw on-chain integer (wei for ETH, base units for stables) at
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

  // Pre-select ETH when payment options first arrive — saves the user a click
  // for the most common case. Falls back to leaving everything unselected if
  // ETH isn't offered (oracle divergence, chain disabled, etc.); the user
  // picks an asset manually then. Only fires when nothing has been picked yet
  // so we don't clobber an explicit user choice on a re-render.
  useEffect(() => {
    if (tokenFilter !== null || picked !== null) return
    if (options.length === 0) return
    const firstEth = options.find(o => o.symbol === 'ETH')
    if (!firstEth) return
    setTokenFilter('ETH')
    setPicked(firstEth)
  }, [options, tokenFilter, picked])
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)
  // Confirmation progress surfaced from the backend's `confirmations` /
  // `confirmations_required` fields. Used to render "Confirming on-chain
  // (X/N)" instead of an opaque spinner during the verify poll.
  const [confirmProgress, setConfirmProgress] = useState<{ current: number; required: number } | null>(null)

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
  // TEMPORARY — REMOVE AFTER TESTING. Lets us force the recovery wrapper
  // into one of three modes without touching the code each time:
  //   normal: wallet returns hash → WALLET path wins
  //   no-hash: wallet hash is discarded → DISCOVERY path should win
  //   no-hash-no-discovery: discovery also stubbed → MANUAL path is the only way
  const [simulateMode, setSimulateMode] = useState<'normal' | 'no-hash' | 'no-hash-no-discovery'>('normal')

  const { address, chainId: walletChainId, connector } = useAccount()
  const { walletInfo } = useWalletInfo()
  const connectionKind = classifyConnection(connector)
  const connectedWalletName = walletInfo?.name || connector?.name
  const { signMessageAsync } = useSignMessage()
  const { switchChainAsync } = useSwitchChain()
  const { writeContractAsync } = useWriteContract()
  const { sendTransactionAsync } = useSendTransaction()

  // Pull per-(chain, token) balances for the connected wallet so we can show
  // them in the picker and grey out rows the user can't afford. Plugin uses
  // Zapper-first / RPC-fallback (same engine the x402 endpoint uses).
  const balancesQuery = useWalletBalances(config, address)

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

  const { organizer, event } = parseOrgAndEvent()

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

    while (Date.now() - startedAt < budget) {
      await new Promise((r) => setTimeout(r, interval))
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
        const body = await r.json()
        if (body.verified) {
          setConfirmProgress(null)
          return
        }
      } else {
        const body = await r.json().catch(() => ({} as { error?: string; confirmations?: number | null; confirmations_required?: number | null }))
        const errMsg = (body.error as string | undefined) || `verify HTTP ${r.status}`
        if (!RETRYABLE_ERROR_SUBSTRINGS.some((s) => errMsg.includes(s))) {
          setConfirmProgress(null)
          throw new Error(errMsg)
        }
        // Update progress + recompute budget once we know the chain's threshold.
        const cur = typeof body.confirmations === 'number' ? body.confirmations : null
        const req = typeof body.confirmations_required === 'number' ? body.confirmations_required : null
        if (cur !== null && req !== null) {
          setConfirmProgress({ current: cur, required: req })
          budget = pollMaxDurationMs(q.chain_id, req)
        }
      }
    }
    setConfirmProgress(null)
    throw new Error('Verification timed out. Try submitting the transaction hash manually below.')
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
  // Validates the pasted hash on-chain (from=payer, nonce=expectedNonce
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

    try {
      // Step 1: Get challenge
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
        throw new Error(body.error || `challenge HTTP ${cr.status}`)
      }
      const { nonce, message } = await cr.json()

      // Step 2: Sign challenge
      setStatus('signing-challenge')
      const signature = await signMessageAsync({ message })

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
        throw new Error(body.error || `create-quote HTTP ${qr.status}`)
      }
      const q: Quote = await qr.json()
      setQuote(q)

      // Step 4: Switch chain if needed.
      //
      // Some WalletConnect wallets (Trust Wallet, Bitget Mobile) only show
      // the FIRST chain in the handshake UI, so the buyer's session ends
      // up scoped to Ethereum only. When we ask to switch to another
      // chain the wallet returns DISAPPROVED_CHAINS / 5100 (or just no-
      // ops) and `switchChainAsync` throws. The downstream
      // `sendTransactionAsync({ chainId })` / `writeContractAsync({
      // chainId })` will also throw with a chain-mismatch error so the
      // wrong-chain payment can never go through — but the buyer sees a
      // raw "user rejected request" message and has no idea what's
      // going on. Catch the switch error specifically and surface a
      // remediation: disconnect, reconnect, approve all networks during
      // the handshake.
      if (walletChainId !== q.chain_id) {
        setStatus('switching')
        try {
          await switchChainAsync({ chainId: q.chain_id })
        } catch (switchErr) {
          const isWc = connectionKind === 'walletConnect'
          // `Quote` carries chain_id only, not the human name — pull the
          // friendly name off the user's picked option (same payload that
          // built the quote, present in the same scope) and fall back to
          // the chain id if the option somehow isn't available.
          const chainName = picked?.chain_name ?? `chain ${q.chain_id}`
          throw new Error(
            isWc
              ? `Your wallet refused to switch to ${chainName}. This usually means the WalletConnect session was approved for Ethereum only. Disconnect (button at the top), reconnect, and approve all networks listed in your wallet's prompt — then retry the payment.`
              : `Couldn't switch your wallet to ${chainName}. Please switch manually in your wallet and try again.`,
          )
        }
      }

      // Step 5: Send tx
      setStatus('signing-tx')

      // Capture the payer's pending-nonce BEFORE broadcast — the value the
      // wallet is about to use. Used by waitForReceiptOrReplacement so the
      // nonce-based fallback works even if our chain RPC never sees the
      // original tx hash (wallet broadcast on a different RPC; user clicked
      // "Speed Up" before viem's getTransaction could populate).
      let expectedNonce: number | undefined
      try {
        expectedNonce = await getTransactionCount(wagmiConfig, {
          address: address as `0x${string}`,
          blockTag: 'pending',
          chainId: q.chain_id,
        })
      } catch {
        // Best-effort — without this, the helper falls back to its own
        // discovery path. Don't block the broadcast on a transient RPC error.
      }

      // Route the wallet send through the recovery wrapper so wallets that
      // broadcast but never return the hash via WC (Binance Wallet macOS,
      // etc.) don't strand the UI in "Confirm payment in wallet…" forever.
      // The wrapper races the wallet's promise vs nonce-based discovery vs
      // a manual-hash escape hatch.
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
      const txHash: string = await sendWithRecovery({
        walletSend,
        payer: address as `0x${string}`,
        chainId: q.chain_id,
        expectedNonce,
      })

      // Step 6: wait for the tx to actually be mined before telling the
      // backend to verify. `sendTransactionAsync` resolves on broadcast, not
      // on inclusion — calling verify before the block is produced used to
      // surface as `RPC error: transaction with hash ... not found`.
      //
      // viem's built-in replacement detection in `waitForTransactionReceipt`
      // requires that we can resolve the original tx's `from`+`nonce` via
      // our chain RPC. That fails when the wallet broadcast through its own
      // RPC and ours hasn't seen the tx yet — the user clicks "Speed Up"
      // before viem ever fetched the original, and viem then has nothing to
      // diff against. Symptom: page hangs forever on the orphaned hash.
      //
      // Fix: race two strategies and take whichever resolves first.
      //   (a) viem's onReplaced-aware `waitForTransactionReceipt`
      //   (b) a nonce-based watcher that polls `getTransactionCount(latest)`
      //       for the payer until it advances past the broadcast nonce, then
      //       walks recent blocks for the actual hash at that nonce
      // We also pre-fetch the tx info up-front (with retries) so viem's
      // internal cache has a real chance to populate before any speed-up.
      let minedHash = txHash
      try {
        const result = await waitForReceiptOrReplacement({
          wagmiConfig,
          chainId: q.chain_id,
          hash: txHash as `0x${string}`,
          payer: address as `0x${string}`,
          expectedNonce,
        })
        minedHash = result.hash
        if (minedHash !== txHash) {
          // eslint-disable-next-line no-console
          console.info('[wc_inject] tx replaced/sped-up:', txHash, '→', minedHash)
        }
        if (result.cancelled) {
          throw new Error(`Transaction was cancelled ${walletLocationPhrase(connectionKind, connectedWalletName)} — please retry.`)
        }
      } catch (e) {
        const msg = (e as Error).message ?? ''
        // Match the cancellation prefix produced just above (the suffix is
        // wallet-specific now — "in MetaMask", "in Rainbow on your phone",
        // etc. — so the old `includes('cancelled in your wallet')` check
        // would silently miss it).
        if (msg.startsWith('Transaction was cancelled')) throw e
        // Otherwise: indexer lag / network blip — fall through; pollVerify's
        // retry loop will pick it up. We keep `minedHash = txHash` since we
        // weren't able to detect a replacement.
      }

      // Step 7: Verify
      setStatus('verifying')
      await pollVerify(q, minedHash)
      onConfirmed(minedHash, q)
    } catch (e: unknown) {
      const err = e as { shortMessage?: string; message?: string }
      setError(err.shortMessage || err.message || String(e))
      setStatus('error')
    }
  }

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
        // Once the backend has reported `confirmations`, surface the
        // progress fraction so users see motion instead of a stalled spinner
        // (especially on Ethereum L1 where 3 confs \u2248 36 s).
        if (confirmProgress) {
          return `Confirming on-chain (${confirmProgress.current}/${confirmProgress.required})\u2026`
        }
        return 'Verifying on-chain\u2026'
      case 'error': return 'Retry'
    }
  })()

  const busy = status !== 'idle' && status !== 'error'

  return (
    <div className="wc-root">
      <WalletHeader disabled={busy} />

      <h3 style={{ marginTop: 0 }}>Select payment method</h3>

      {/* DEBUG — uncomment to re-test the tx-hash recovery paths without
          rebuilding new code. Forces the recovery wrapper into a specific
          path. The supporting state (simulateMode), wrapper branches, and
          .wc-debug-* CSS are left in place so this is a one-block re-enable.
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
      </div>
      */}

      {!ethAvailable && ethDisabledReason && (
        <div className="wc-notice">
          {ethReasonText(
            ethDisabledReason,
            // Stables actually offered by this event (= options minus ETH).
            // Keeps the suggestion in sync with the plugin's chain/token toggles.
            [...new Set(options.filter(o => o.symbol !== 'ETH').map(o => o.symbol))],
          )}
        </div>
      )}

      {options.length === 0 && (
        <div className="wc-error">No payment options available.</div>
      )}

      {/* Step 1: Token selection chips */}
      {(() => {
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
                      if (first) setPicked(first)
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
                <span className="wc-network-label">Network</span>
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
                    const balanceDisplay = balanceEntry
                      ? `${formatBalance(balanceEntry.balance, balanceEntry.decimals)} ${opt.symbol}`
                      : null
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
                        onClick={() => setPicked(opt)}
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

      {quote && (
        <p className="wc-small" style={{ marginTop: 8 }}>
          Amount: <strong>{formatAmount(quote)}</strong> to <code style={{ wordBreak: 'break-all' }}>{quote.receive_address}</code>
        </p>
      )}

      {/* Hide the Pay button entirely while the wallet is disconnected. The
          parent `WCPaymentApp` should already flip the stage back to 'connect'
          on disconnect, but this is a defensive render guard for the brief
          window between the disconnect event firing and the stage transition,
          and for any edge case where `address` is undefined without the
          component unmounting. */}
      {address && (
        <button
          type="button"
          className="btn btn-primary btn-lg btn-block wc-pay-btn"
          disabled={!picked || busy}
          onClick={handlePay}
        >
          {buttonLabel}
        </button>
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
          from their wallet's history; we validate it on-chain (correct
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

      {error && <div className="wc-error">{error}</div>}

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
          `Wallet address: ${fill(address || '')}`,
          `Network: ${fill(networkValue)}`,
          `Token: ${fill(tokenValue)}`,
          `Amount sent: ${fill(amountValue)}`,
          `Recipient: ${fill(recipientValue)}`,
          `Transaction hash: (paste the 0x\u2026 hash from your wallet here)`,
          "",
          "Thanks!",
        ]
        const mailtoHref = config.supportEmail
          ? `mailto:${config.supportEmail}?subject=${encodeURIComponent(
              `Payment issue for order ${config.orderCode}`,
            )}&body=${encodeURIComponent(lines.join('\n'))}`
          : null
        return (
          <div className="wc-support-block" style={{ marginTop: 16, padding: 12, background: '#f7f5ff', borderRadius: 8 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Already sent the transaction?</div>
            <div style={{ fontSize: 14, lineHeight: 1.4 }}>
              <strong>Don't re-send</strong> — you'd be charged twice.
              {' '}
              {mailtoHref ? (
                <>
                  <a href={mailtoHref}>Email the event organizer</a> — we've pre-filled everything we know; just add your transaction hash and send.
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
        const mailtoHref = `mailto:${config.supportEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n'))}`
        return (
          <div className="wc-support-pill">
            <p>
              Need help?{' '}
              <a href={mailtoHref}>
                <strong>Contact support</strong>
              </a>
            </p>
          </div>
        )
      })()}
    </div>
  )
}
