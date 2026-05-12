import { appKitInstance } from '../config'

export function ConnectStep() {
  // ── Mobile Coinbase / Base Account escape hatch ──
  // iOS Safari evicts the WebView when CB Wallet takes foreground via a
  // Universal Link during signMessage; the page reloads mid-flow and
  // the buyer's React state (selection, quote, etc.) is lost. The
  // single environment where this works on mobile is *inside* the CB
  // Wallet app's in-app browser, where signing is local. We hide CB
  // from the AppKit picker on mobile Safari (in config.ts) and surface
  // a separate deep-link button here that opens the current Pretix
  // checkout URL — which already contains `order_code` + `order_secret`
  // in the path — inside the CB Wallet embed browser via the universal
  // `go.cb-w.com/dapp?cb_url=` endpoint. Inside the embed browser the
  // CB entry stays visible (no need for this banner).
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent || '' : ''
  const isMobile = /iPhone|iPad|iPod|Android/i.test(ua)
  const inCoinbaseEmbed = /Coinbase/i.test(ua)
  const showCbEmbedLink = isMobile && !inCoinbaseEmbed
  const cbDappUrl = typeof window !== 'undefined'
    ? `https://go.cb-w.com/dapp?cb_url=${encodeURIComponent(window.location.href)}`
    : ''

  return (
    <div className="wc-root">
      <h3 style={{ marginTop: 0 }}>Pay with crypto</h3>
      <p>Connect your wallet to continue. Supports MetaMask, Rainbow, Coinbase Wallet, WalletConnect, and more.</p>
      <button
        type="button"
        className="btn btn-primary btn-lg btn-block wc-pay-btn"
        onClick={() => appKitInstance?.open()}
      >
        Connect wallet
      </button>
      {showCbEmbedLink && (
        <div className="wc-cb-embed-block">
          <p className="wc-cb-embed-hint">
            Want to pay with Coinbase / Base Smart Wallet?
          </p>
          <a
            href={cbDappUrl}
            className="wc-cb-embed-link"
            rel="noopener noreferrer"
          >
            Open this page in the Coinbase Wallet app →
          </a>
        </div>
      )}
    </div>
  )
}
