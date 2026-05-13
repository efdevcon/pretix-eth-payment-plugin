import { useEffect, useState } from 'react'
import { useAccount } from 'wagmi'
import type { WCConfig } from './config'
import { ConnectStep } from './components/ConnectStep'
import { CheckoutStep } from './components/CheckoutStep'
import { SuccessStep } from './components/SuccessStep'
import { usePaymentOptions } from './hooks/usePaymentOptions'

type Stage = 'connect' | 'checkout' | 'success'

export interface Quote {
  quote_id: string
  chain_id: number
  symbol: string
  token_address: string | null
  amount_raw: string
  receive_address: string
  intended_payer: string
  expires_at: number
  eth_price_usd: number | null
  order_total_usd: string
}

export function WCPaymentApp({ config }: { config: WCConfig }) {
  const account = useAccount()
  const [stage, setStage] = useState<Stage>('connect')
  const [txHash, setTxHash] = useState<string | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)
  const opts = usePaymentOptions(config)

  useEffect(() => {
    if (account.isConnected && stage === 'connect') setStage('checkout')
    if (!account.isConnected && stage !== 'connect') setStage('connect')
  }, [account.isConnected, stage])

  // Apply `wc-full-checkout` at the top level (not per-stage). styles.css uses
  // this class to hide Pretix's native submit button whenever our UI owns the
  // page — we need that coverage while the wallet is disconnected too, otherwise
  // Pretix's own "Pay now" flashes in the gap between our ConnectStep render
  // and the user reconnecting their wallet.
  useEffect(() => {
    document.body.classList.add('wc-full-checkout')
    return () => { document.body.classList.remove('wc-full-checkout') }
  }, [])

  if (stage === 'connect') return <ConnectStep config={config} />

  if (stage === 'checkout') {
    if (opts.isLoading) return <div className="wc-root wc-small">Loading payment options...</div>
    if (opts.isError || !opts.data) return <div className="wc-root wc-error">Failed to load payment options.</div>
    return (
      <CheckoutStep
        config={config}
        options={opts.data.options}
        ethAvailable={opts.data.eth_available}
        ethDisabledReason={opts.data.eth_disabled_reason}
        ethPriceUsd={opts.data.eth_price_usd}
        chainMetadata={opts.data.chain_metadata}
        onConfirmed={(hash, q) => { setTxHash(hash); setQuote(q); setStage('success') }}
      />
    )
  }

  if (stage === 'success' && quote && txHash) {
    return <SuccessStep quote={quote} txHash={txHash} />
  }

  return null
}
