import { useEffect, useRef, useState } from 'react'
import { useAccount } from 'wagmi'
import type { WCConfig } from './config'
import { ConnectStep } from './components/ConnectStep'
import { CheckoutStep } from './components/CheckoutStep'
import { LoadingState } from './components/LoadingState'
import { usePaymentOptions } from './hooks/usePaymentOptions'

type Stage = 'connect' | 'checkout' | 'disconnecting'

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

// How long the explicit "Disconnecting…" loader is held after wagmi
// flips isConnected from true to false. Long enough to register a clean
// transition (instead of a hard CheckoutStep → ConnectStep cut, which
// previously read as a flicker), short enough not to feel sluggish.
const DISCONNECT_LOADER_MS = 500

export function WCPaymentApp({ config }: { config: WCConfig }) {
  const account = useAccount()
  const opts = usePaymentOptions(config)

  // Show a brief loading frame when the user disconnects, so the
  // transition is "connected UI → loader → ConnectStep" rather than a
  // hard cut. Detection keys off wagmi's `status` (rather than the
  // boolean `isConnected`) so we can distinguish a real user disconnect
  // (`connected` → `disconnected`) from wagmi's own reconnect handshake
  // on page load (`reconnecting` → `connected` or `reconnecting` →
  // `disconnected`). The `hasMountedRef` guard skips the very first
  // effect run so neither initial-load transition can trigger the
  // loader either.
  const hasMountedRef = useRef(false)
  const prevStatusRef = useRef<typeof account.status>(account.status)
  const [disconnecting, setDisconnecting] = useState(false)

  // Detection effect — sets the disconnecting flag only on the
  // `connected` → `disconnected` edge, and only after the component
  // has settled (one full render cycle past mount).
  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true
      prevStatusRef.current = account.status
      return
    }
    const wasConnected = prevStatusRef.current === 'connected'
    prevStatusRef.current = account.status
    if (wasConnected && account.status === 'disconnected') {
      setDisconnecting(true)
    }
  }, [account.status])

  // Clearing effect — guarantees the loader resolves:
  //   (a) after DISCONNECT_LOADER_MS via setTimeout, OR
  //   (b) immediately if the user reconnects mid-window.
  // No matter what wagmi/AppKit do, this effect always converges back
  // to disconnecting=false.
  useEffect(() => {
    if (!disconnecting) return
    if (account.isConnected) {
      setDisconnecting(false)
      return
    }
    const t = setTimeout(() => setDisconnecting(false), DISCONNECT_LOADER_MS)
    return () => clearTimeout(t)
  }, [disconnecting, account.isConnected])

  // Stage derived synchronously. `disconnecting` wins over `connect` so
  // the loader covers the brief window while wagmi finishes tearing
  // down the connector and any AppKit cleanup completes. Success is
  // handled inline by CheckoutStep (no separate stage needed).
  const stage: Stage = disconnecting
    ? 'disconnecting'
    : account.isConnected
      ? 'checkout'
      : 'connect'

  // Apply `wc-full-checkout` at the top level (not per-stage). styles.css uses
  // this class to hide Pretix's native submit button whenever our UI owns the
  // page — we need that coverage while the wallet is disconnected too, otherwise
  // Pretix's own "Pay now" flashes in the gap between our ConnectStep render
  // and the user reconnecting their wallet.
  useEffect(() => {
    document.body.classList.add('wc-full-checkout')
    return () => { document.body.classList.remove('wc-full-checkout') }
  }, [])

  // Remove the static boot loader once React has actually painted. Doing
  // this here (in a mount effect) rather than synchronously in index.tsx
  // guarantees there's no empty-frame gap on slow connections — the
  // boot loader stays visible until React has something to swap in.
  useEffect(() => {
    document.getElementById('wc-boot-loading')?.remove()
  }, [])

  if (stage === 'disconnecting') return <LoadingState message="Disconnecting your wallet…" />
  if (stage === 'connect') return <ConnectStep config={config} />

  if (stage === 'checkout') {
    if (opts.isLoading) return <LoadingState message="Loading payment options…" />
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
