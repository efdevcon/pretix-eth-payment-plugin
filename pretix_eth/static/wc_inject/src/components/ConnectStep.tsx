import { appKitInstance, type WCConfig } from '../config'

export function ConnectStep({ config }: { config?: WCConfig } = {}) {
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
      {/* The CB Wallet in-app-browser deep-link banner was previously shown
          here unconditionally for any mobile user, which was noise for the
          ~95% of buyers using MetaMask / Rainbow / etc. The same hint now
          surfaces in CheckoutStep only when `connectionKind === 'coinbaseWallet'`
          — i.e. only buyers who actually picked CBSW from the AppKit modal
          and would otherwise hit Safari's WebView eviction issue see it. */}
    </div>
  )
}
