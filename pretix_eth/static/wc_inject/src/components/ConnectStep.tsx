import { appKitInstance, type WCConfig } from '../config'

export function ConnectStep({ config }: { config?: WCConfig } = {}) {
  // Mobile-Safari escape hatch: deep-link the current Pretix checkout URL
  // into the CB Wallet in-app browser (local signing, no WebView eviction).
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent || '' : ''
  const showCbEmbedLink = /iPhone|iPad|iPod|Android/i.test(ua) && !/Coinbase/i.test(ua)
  const cbDappUrl = typeof window !== 'undefined'
    ? `https://go.cb-w.com/dapp?cb_url=${encodeURIComponent(window.location.href)}`
    : ''

  // When the event has ETH-on-mainnet as the only enabled option (wave
  // launch), name the chain in the heading.
  const heading = config?.ethMainnetOnly ? 'Pay with ETH' : 'Pay with crypto'

  return (
    <div className="wc-root">
      <h3 style={{ marginTop: 0 }}>{heading}</h3>
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
