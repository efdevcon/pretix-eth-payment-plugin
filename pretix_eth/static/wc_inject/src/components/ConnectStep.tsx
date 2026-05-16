import { appKitInstance, type WCConfig } from '../config'

const FIND_WALLET_URL = 'https://ethereum.org/wallets/find-wallet/'

export function ConnectStep({ config }: { config?: WCConfig } = {}) {
  // When the event has ETH-on-mainnet as the only enabled option (wave
  // launch), name the chain in the heading. Otherwise fall back to a
  // generic "crypto" label — the picker on the next step shows the full
  // token list.
  const heading = config?.ethMainnetOnly ? 'Pay with ETH' : 'Pay with crypto'
  const tokenBullet = config?.ethMainnetOnly ? 'Pay with ETH' : 'Pay with crypto'

  return (
    <div className="wc-root wc-connect-step">
      <h3 className="wc-connect-heading">{heading}</h3>
      <p className="wc-connect-sub">
        Connect your wallet to continue. Supports MetaMask, Rainbow, Coinbase Wallet, WalletConnect, and more.
      </p>
      {/* Value-prop row — three short reassurances right above the CTA so
          the buyer's first 2-second impression conveys confidence. The
          middle bullet links out to Ethereum.org's wallet finder for any
          buyer who doesn't yet have a wallet installed. */}
      <ul className="wc-value-props" aria-label="Payment summary">
        <li>{tokenBullet}</li>
        <li>
          <a href={FIND_WALLET_URL} target="_blank" rel="noopener noreferrer">
            Any major wallet
          </a>
        </li>
        <li>Verified on-chain</li>
      </ul>
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
