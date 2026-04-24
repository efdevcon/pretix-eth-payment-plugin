import { useState, useEffect } from 'react'
import {
  useAccount,
  useSignMessage,
  useSwitchChain,
  useWriteContract,
  useSendTransaction,
  useConfig,
} from 'wagmi'
import { waitForTransactionReceipt } from 'wagmi/actions'
import { erc20Abi } from 'viem'
import { NETWORK_LOGOS, TOKEN_LOGOS } from '../assetIcons'
import type { WCConfig } from '../config'
import type { PaymentOption } from '../hooks/usePaymentOptions'
import type { Quote } from '../WCPaymentApp'
import { WalletHeader } from './WalletHeader'

const MAX_VERIFY_ATTEMPTS = 8
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

const ETH_REASON_TEXT: Record<string, string> = {
  oracle_unavailable_or_diverged:
    'ETH payments temporarily unavailable. Our price oracles (Coinbase, Binance) disagree by more than 5% or are unreachable. Please pay with USDC or USDT0 instead.',
  oracle_error:
    'ETH payments temporarily unavailable due to a price lookup error. Please pay with USDC or USDT0 instead.',
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

function formatAmount(q: Quote): string {
  if (q.symbol === 'ETH') {
    const eth = Number(BigInt(q.amount_raw)) / 1e18
    return `${eth.toFixed(6)} ETH`
  }
  const usd = Number(BigInt(q.amount_raw)) / 1e6
  return `${usd.toFixed(2)} ${q.symbol}`
}

export function CheckoutStep({
  config,
  options,
  ethAvailable,
  ethDisabledReason,
  chainMetadata,
  onConfirmed,
}: {
  config: WCConfig
  options: PaymentOption[]
  ethAvailable: boolean
  ethDisabledReason: string | null
  chainMetadata: Record<string, { name: string; explorer_url: string }>
  onConfirmed: (txHash: string, quote: Quote) => void
}) {
  const [tokenFilter, setTokenFilter] = useState<string | null>(null)
  const [picked, setPicked] = useState<PaymentOption | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)

  const { address, chainId: walletChainId } = useAccount()
  const { signMessageAsync } = useSignMessage()
  const { switchChainAsync } = useSwitchChain()
  const { writeContractAsync } = useWriteContract()
  const { sendTransactionAsync } = useSendTransaction()
  // Use the wagmi `config` imperatively via `waitForTransactionReceipt` so we
  // can target the quote's chainId explicitly. Necessary because the user's
  // wallet may have been on a different chain when this component mounted;
  // a chain-scoped hook captured at render time would query the wrong RPC.
  const wagmiConfig = useConfig()

  const { organizer, event } = parseOrgAndEvent()

  // Hide Pretix's native submit button when our full checkout UI is active
  useEffect(() => {
    document.body.classList.add('wc-full-checkout')
    return () => { document.body.classList.remove('wc-full-checkout') }
  }, [])

  async function pollVerify(q: Quote, txHash: string) {
    for (let attempt = 0; attempt < MAX_VERIFY_ATTEMPTS; attempt++) {
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)))
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
        if (body.verified) return
      } else {
        const body = await r.json().catch(() => ({}))
        const errMsg = (body.error as string | undefined) || `verify HTTP ${r.status}`
        if (!RETRYABLE_ERROR_SUBSTRINGS.some((s) => errMsg.includes(s))) {
          throw new Error(errMsg)
        }
      }
    }
    throw new Error('Verification timed out. Try submitting the transaction hash manually below.')
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

      // Step 3: Create quote
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
        }),
      })
      if (!qr.ok) {
        const body = await qr.json().catch(() => ({}))
        throw new Error(body.error || `create-quote HTTP ${qr.status}`)
      }
      const q: Quote = await qr.json()
      setQuote(q)

      // Step 4: Switch chain if needed
      if (walletChainId !== q.chain_id) {
        setStatus('switching')
        await switchChainAsync({ chainId: q.chain_id })
      }

      // Step 5: Send tx
      setStatus('signing-tx')
      let txHash: string
      if (q.symbol === 'ETH') {
        txHash = await sendTransactionAsync({
          to: q.receive_address as `0x${string}`,
          value: BigInt(q.amount_raw),
          chainId: q.chain_id,
        })
      } else {
        if (!q.token_address) throw new Error('token_address missing')
        txHash = await writeContractAsync({
          address: q.token_address as `0x${string}`,
          abi: erc20Abi,
          functionName: 'transfer',
          args: [q.receive_address as `0x${string}`, BigInt(q.amount_raw)],
          chainId: q.chain_id,
        })
      }

      // Step 6: wait for the tx to actually be mined before telling the
      // backend to verify. `sendTransactionAsync` resolves on broadcast, not
      // on inclusion — calling verify before the block is produced used to
      // surface as `RPC error: transaction with hash ... not found`.
      try {
        await waitForTransactionReceipt(wagmiConfig, {
          hash: txHash as `0x${string}`,
          chainId: q.chain_id,
        })
      } catch {
        // Fall through to pollVerify, whose retry loop will pick up any
        // lingering indexer lag.
      }

      // Step 7: Verify
      setStatus('verifying')
      await pollVerify(q, txHash)
      onConfirmed(txHash, q)
    } catch (e: unknown) {
      const err = e as { shortMessage?: string; message?: string }
      setError(err.shortMessage || err.message || String(e))
      setStatus('error')
    }
  }

  const buttonLabel = (() => {
    switch (status) {
      case 'idle': return 'Pay now'
      case 'challenge': return 'Preparing\u2026'
      case 'signing-challenge': return 'Sign message in wallet\u2026'
      case 'quoting': return 'Creating quote\u2026'
      case 'switching': return 'Switching chain\u2026'
      case 'signing-tx': return 'Confirm payment in wallet\u2026'
      case 'verifying': return 'Verifying on-chain\u2026'
      case 'error': return 'Retry'
    }
  })()

  const busy = status !== 'idle' && status !== 'error'

  return (
    <div className="wc-root">
      <WalletHeader />

      <h3 style={{ marginTop: 0 }}>Select payment method</h3>

      {!ethAvailable && ethDisabledReason && (
        <div className="wc-notice">
          {ETH_REASON_TEXT[ethDisabledReason] || 'ETH payments temporarily unavailable.'}
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
                    return (
                      <button
                        key={`${opt.chain_id}-${opt.symbol}`}
                        type="button"
                        className={`wc-network-row ${isSelected ? 'wc-network-row--selected' : ''}`}
                        disabled={busy}
                        onClick={() => setPicked(opt)}
                      >
                        <span className="wc-network-row-left">
                          {logo && (
                            <img src={logo} alt="" className="wc-network-icon" aria-hidden="true" />
                          )}
                          <span className="wc-network-row-name">{opt.chain_name}</span>
                        </span>
                        {isSelected && <span className="wc-network-row-check">&#10003;</span>}
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
    </div>
  )
}
