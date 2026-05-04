import { useAccount, useDisconnect } from 'wagmi'

export function WalletHeader({ disabled = false }: { disabled?: boolean }) {
  const { address } = useAccount()
  const { disconnect } = useDisconnect()

  if (!address) return null

  const short = `${address.slice(0, 6)}...${address.slice(-4)}`

  return (
    <div className="wc-wallet-header">
      <span className="wc-small">
        Connected: <code>{short}</code>
      </span>
      <button
        className="wc-link-button"
        onClick={() => disconnect()}
        // Lock disconnect mid-flight: swapping wallets during tx-broadcast
        // or the verify poll leaves the backend tracking the original payer
        // while the UI reflects a different session. Caller passes `disabled`
        // bound to the parent's busy flag so the button is greyed out from
        // first sign through verify-success.
        disabled={disabled}
        title={disabled ? 'Disconnect disabled while a payment is being verified.' : undefined}
      >
        Disconnect
      </button>
    </div>
  )
}
