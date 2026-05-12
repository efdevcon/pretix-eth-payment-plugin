/** Helpers for surfacing *which* wallet the buyer is connected through —
 *  mainly so a returning user with a stale WalletConnect session sees the
 *  actual wallet name (e.g. "Rainbow") and connection type, not just an
 *  address, and knows which app to open before clicking Pay.
 *
 *  Mirrors the same module in devcon-next (`src/utils/walletConnection.ts`).
 *  Kept duplicated rather than shared because wc_inject is bundled
 *  separately and shipped inside the Pretix plugin static dir.
 */

export type ConnectionKind = 'injected' | 'walletConnect' | 'coinbaseWallet' | 'safe' | 'other'

/** Map a wagmi connector to a connection kind. Prefers `connector.type`
 *  because it's the stable signal across EIP-6963-detected wallets —
 *  Zerion / Rainbow / Phantom / Trust / Frame extensions come through
 *  with `id: '<rdns>'` (e.g. 'io.zerion.wallet') but `type: 'injected'`.
 *  Matching on `id` alone drops them into the `'other'` bucket. */
export function classifyConnection(
  connector: { id?: string; type?: string } | undefined,
): ConnectionKind {
  if (!connector) return 'other'
  switch (connector.type) {
    case 'injected': return 'injected'
    case 'walletConnect': return 'walletConnect'
    // `baseAccount` is the modern Base Account / Coinbase Smart Wallet
    // connector (wagmi/@wagmi/connectors `baseAccount()`), which Reown
    // AppKit auto-installs since 1.8.x. `coinbaseWallet` is the legacy
    // SDK4 connector. Treat both as the same connection kind — the UI
    // copy ("Approve in Coinbase Wallet") and the post-sign send path
    // (EIP-5792 capability probe → `sendCalls`) apply uniformly.
    case 'coinbaseWallet': return 'coinbaseWallet'
    case 'baseAccount': return 'coinbaseWallet'
    case 'safe': return 'safe'
  }
  const id = connector.id
  if (!id) return 'other'
  if (id === 'injected' || id === 'metaMask' || id === 'metaMaskSDK') return 'injected'
  if (id === 'walletConnect') return 'walletConnect'
  if (id === 'coinbaseWallet' || id === 'coinbaseWalletSDK' || id === 'baseAccount') return 'coinbaseWallet'
  if (id === 'safe') return 'safe'
  return 'other'
}

export function connectionTypeLabel(kind: ConnectionKind): string {
  switch (kind) {
    case 'injected': return 'Browser extension'
    case 'walletConnect': return 'WalletConnect (mobile)'
    case 'coinbaseWallet': return 'Coinbase Wallet'
    case 'safe': return 'Safe multisig'
    default: return 'Connected'
  }
}

/** Lucide icon name for the connection-type pill — kept as a string so
 *  the wc_inject bundle (no Lucide dep) can map to its own glyph. */
export function connectionTypeIcon(kind: ConnectionKind): 'monitor' | 'smartphone' | 'wallet' | 'shield' {
  switch (kind) {
    case 'injected': return 'monitor'
    case 'walletConnect': return 'smartphone'
    case 'coinbaseWallet': return 'wallet'
    case 'safe': return 'shield'
    default: return 'wallet'
  }
}

export function preSignHint(kind: ConnectionKind, walletName: string | undefined): string {
  const name = walletName || fallbackName(kind)
  switch (kind) {
    case 'walletConnect':
      return `Open ${name} on your phone to approve.`
    case 'injected':
      return `Approve the request in your ${name} popup.`
    case 'coinbaseWallet':
      return `Approve the request in Coinbase Wallet.`
    case 'safe':
      return `Open the Safe app to queue and sign this transaction.`
    default:
      return `Approve the request in your wallet.`
  }
}

/** Phrase like "in Rainbow on your phone" or "in MetaMask" — slots into
 *  imperative status strings so a buyer knows where the next action is
 *  happening (mirror of the same helper in devcon-next). */
export function walletLocationPhrase(kind: ConnectionKind, walletName: string | undefined): string {
  const name = walletName || fallbackName(kind)
  switch (kind) {
    case 'walletConnect':
      return `in ${name} on your phone`
    case 'injected':
      return `in ${name}`
    case 'coinbaseWallet':
      return `in Coinbase Wallet`
    case 'safe':
      return `in your Safe app`
    default:
      return `in your wallet`
  }
}

function fallbackName(kind: ConnectionKind): string {
  switch (kind) {
    case 'walletConnect': return 'your wallet app'
    case 'injected': return 'wallet'
    case 'coinbaseWallet': return 'Coinbase Wallet'
    case 'safe': return 'Safe'
    default: return 'wallet'
  }
}
