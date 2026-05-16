import { appKitInstance, type WCConfig } from '../config'

const FIND_WALLET_URL = 'https://ethereum.org/wallets/find-wallet/'
const GET_ETH_URL = 'https://ethereum.org/get-eth/'

// Lucide-style line icons inlined as SVG (no runtime dep, ~0.5 KB total).
// Stroke uses currentColor so the parent's color setting drives the tint.
function WalletIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" />
      <path d="M3 5v14a2 2 0 0 0 2 2h16v-5" />
      <path d="M18 12a2 2 0 0 0 0 4h4v-4h-4z" />
    </svg>
  )
}
function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  )
}
function ZapIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  )
}

export function ConnectStep({ config }: { config?: WCConfig } = {}) {
  // When the event has ETH-on-mainnet as the only enabled option (wave
  // launch), name the chain in the heading. Otherwise fall back to a
  // generic "crypto" label — the picker on the next step shows the full
  // token list.
  const heading = config?.ethMainnetOnly ? 'Pay with ETH' : 'Pay with crypto'

  return (
    <div className="wc-root wc-connect-step">
      <h3 className="wc-connect-heading">{heading}</h3>
      {/* Three pill chips with inline SVG icons. Sequential fade-in stagger
          (handled in styles.css via :nth-child) gives the screen kinetic
          energy without being gimmicky. Copy is tight and specific —
          each chip conveys a distinct value, no overlap with the heading
          or the button label. */}
      <div className="wc-features" aria-label="Payment summary">
        <div className="wc-feature">
          <WalletIcon />
          <span>Any wallet</span>
        </div>
        <div className="wc-feature">
          <ShieldIcon />
          <span>Verified onchain</span>
        </div>
        <div className="wc-feature">
          <ZapIcon />
          <span>Settles in seconds</span>
        </div>
      </div>
      <button
        type="button"
        className="btn btn-primary btn-lg btn-block wc-pay-btn"
        onClick={() => appKitInstance?.open()}
      >
        Connect wallet
      </button>
      <div className="wc-connect-helpers">
        <a
          className="wc-find-wallet"
          href={FIND_WALLET_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Don&apos;t have a wallet? →
        </a>
        <a
          className="wc-find-wallet"
          href={GET_ETH_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Where to get ETH? →
        </a>
      </div>
    </div>
  )
}
