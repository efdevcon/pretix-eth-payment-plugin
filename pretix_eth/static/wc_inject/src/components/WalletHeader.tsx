import { useState } from 'react'
import { useAccount, useDisconnect, useEnsName } from 'wagmi'
import { mainnet } from 'viem/chains'
import { useWalletInfo } from '@reown/appkit/react'
import { classifyConnection, connectionTypeLabel } from '../walletConnection'

export function WalletHeader({ disabled = false }: { disabled?: boolean }) {
  const { address, connector } = useAccount()
  const { walletInfo } = useWalletInfo()
  const { disconnect } = useDisconnect()
  // Some wallets (Bitget chronically, but it's a generic problem with
  // self-hosted icon CDNs) return an `icon` URL that 4xxs or times out;
  // without a fallback the user sees the browser's broken-image glyph.
  // Track the failed URL so we can hide the <img> on subsequent renders.
  const [iconLoadFailedFor, setIconLoadFailedFor] = useState<string | null>(null)
  // Reverse-resolve the connected address to an ENS name on mainnet.
  // Pinned to chainId=1 regardless of which chain the user is paying on
  // because `.eth` reverse records only live on mainnet. Wagmi caches the
  // result via React Query, so this fires once per address.
  const { data: ensName } = useEnsName({
    address,
    chainId: mainnet.id,
    query: { enabled: Boolean(address) },
  })

  if (!address) return null

  const short = `${address.slice(0, 6)}...${address.slice(-4)}`
  // DEMO HARDCODE: rebrand `d.krux.eth` → `d.devcon.eth` for the demo.
  // The `title={address}` on the `<code>` below still surfaces the real
  // 0x on hover, so this is purely a visual substitution. REMOVE AFTER DEMO.
  const rebrandedEns = ensName === 'd.krux.eth' ? 'd.devcon.eth' : ensName
  const displayName = rebrandedEns || short
  // Reown's `useWalletInfo` returns the actual peer wallet over a
  // WalletConnect session (e.g. "Rainbow", "MetaMask Mobile") rather than
  // the generic "WalletConnect" connector name. For injected connections
  // it mirrors the extension's announced metadata. May be undefined for a
  // brief window right after a restored session reconnects — fall back to
  // the connector's own name in that case.
  const walletName = walletInfo?.name || connector?.name
  const walletIcon = walletInfo?.icon
  const kind = classifyConnection(connector)
  const typeLabel = connectionTypeLabel(kind)

  return (
    <div className="wc-wallet-header">
      <div className="wc-wallet-header-info">
        {walletIcon && iconLoadFailedFor !== walletIcon && (
          <img
            src={walletIcon}
            alt={walletName ?? 'wallet'}
            className="wc-wallet-header-icon"
            onError={() => setIconLoadFailedFor(walletIcon)}
          />
        )}
        <div className="wc-wallet-header-meta">
          {walletName && <span className="wc-wallet-header-name">{walletName}</span>}
          <span className="wc-small">
            {/* No "Connected:" prefix — the wallet's own icon to the left
                already conveys the connected state, and the pill below it
                says HOW the wallet is reached. */}
            <code title={address}>{displayName}</code>
            {/* Colored pill that calls out the connection mode at a glance
                — signals "look at your browser" (injected) vs "look at
                your phone" (WC) vs "Safe app" (multisig). data-kind drives
                the tint via CSS in styles.css. */}
            <span className="wc-wallet-header-type" data-kind={kind}>
              {typeLabel}
            </span>
          </span>
        </div>
      </div>
      <button
        type="button"
        className="wc-disconnect-btn"
        onClick={() => disconnect()}
        // `type="button"` is critical — Pretix's checkout-confirm template
        // wraps this whole panel in a <form>, and a bare <button> defaults
        // to type=submit. Without the explicit type, clicking Disconnect
        // would submit Pretix's form, reload the page, and reset scroll
        // to the top.
        //
        // Lock disconnect mid-flight: swapping wallets during tx-broadcast
        // or the verify poll leaves the backend tracking the original payer
        // while the UI reflects a different session. Caller passes `disabled`
        // bound to the parent's busy flag so the button is greyed out from
        // first sign through verify-success.
        disabled={disabled}
        aria-label="Disconnect wallet"
        title={disabled ? 'Disconnect disabled while a payment is being verified.' : 'Disconnect wallet'}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" x2="9" y1="12" y2="12" />
        </svg>
      </button>
    </div>
  )
}
