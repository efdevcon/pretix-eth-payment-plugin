import { useEffect } from 'react'
import { useAccount } from 'wagmi'
import type { WCConfig } from './config'
import { ConnectStep } from './components/ConnectStep'
import { CheckoutStep } from './components/CheckoutStep'
import { usePaymentOptions } from './hooks/usePaymentOptions'

type Stage = 'connect' | 'checkout'

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
  const opts = usePaymentOptions(config)

  // Stage derived synchronously from connection state. Success is handled
  // inline by CheckoutStep (it renders a confirmation card in the same
  // `wc-root` wrapper and triggers its own redirect), so we don't need a
  // separate post-payment stage that swaps the entire view.
  const stage: Stage = account.isConnected ? 'checkout' : 'connect'

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
        onConfirmed={() => {
          // CheckoutStep owns the inline success card + redirect now. This
          // callback is kept on the signature for future hooks (analytics,
          // external observers) but is intentionally a no-op here.
        }}
      />
    )
  }

  return null
}
