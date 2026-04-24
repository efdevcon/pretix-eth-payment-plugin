import { appKitInstance } from '../config'

export function ConnectStep() {
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
    </div>
  )
}
