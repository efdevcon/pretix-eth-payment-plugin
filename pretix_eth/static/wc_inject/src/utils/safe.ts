/**
 * Safe (multisig) integration helpers. Mirrors the storefront's Safe
 * handling in `devcon/src/pages/tickets/store/checkout.tsx` — see that
 * file for the canonical implementation. Only enabled in wc_inject when
 * the event admin flips `safe_payments_enabled` on; gated upstream so
 * none of this code path runs by default.
 */

/** Connector-id / wallet-name heuristic. Covers three shapes:
 *   1. The dedicated `safe` connector (Safe Apps iframe injection).
 *   2. A connector whose `.name` includes "safe" (rare, but covers any
 *      future Safe-branded direct connector).
 *   3. WalletConnect to Safe{Wallet} via Reown's wallet directory — the
 *      connector itself is generic `walletConnect`, the Safe brand only
 *      appears on `useWalletInfo().name` (so the caller has to pass it
 *      in). This is the common production case.
 *  Falls back to `false` for any other shape. */
export function isSafeWallet(
  connector: { id?: string; name?: string } | undefined,
  walletName?: string,
): boolean {
  if (walletName && walletName.toLowerCase().includes('safe')) return true
  if (!connector) return false
  if (connector.id === 'safe') return true
  return Boolean(connector.name?.toLowerCase().includes('safe'))
}

/** Public Safe Transaction Service host per chain (no auth). Returns
 *  null for chains Safe doesn't operate a tx service on. */
export function safeTxServiceHost(chainId: number | undefined): string | null {
  switch (chainId) {
    case 1: return 'safe-transaction-mainnet.safe.global'
    case 10: return 'safe-transaction-optimism.safe.global'
    case 137: return 'safe-transaction-polygon.safe.global'
    case 8453: return 'safe-transaction-base.safe.global'
    case 42161: return 'safe-transaction-arbitrum.safe.global'
    default: return null
  }
}

/** Probe whether `address` is a registered Safe on `chainId`. Returns
 *  the threshold (signatures required) when so, `null` otherwise. */
export async function probeSafe(
  chainId: number | undefined,
  address: string,
): Promise<{ isSafe: true; threshold: number | null } | { isSafe: false }> {
  const host = safeTxServiceHost(chainId)
  if (!host) return { isSafe: false }
  try {
    const res = await fetch(`https://${host}/api/v1/safes/${address}/`)
    if (!res.ok) return { isSafe: false }
    const data = await res.json().catch(() => null)
    return {
      isSafe: true,
      threshold: typeof data?.threshold === 'number' ? data.threshold : null,
    }
  } catch {
    return { isSafe: false }
  }
}

/** Poll Safe Tx Service for the onchain transactionHash after a Safe
 *  has signed/executed a queued transaction. `eth_sendTransaction` on a
 *  Safe returns a *safeTxHash* (offchain) — we translate that to the
 *  real chain hash here so /verify/ has something to look up.
 *
 *  Bails after 10 consecutive 404/422s ("not a Safe, or never broadcast")
 *  or after `budgetMs` of total wall time. */
export async function pollSafeTxService(
  chainId: number | undefined,
  safeTxHash: string,
  budgetMs = 5 * 60_000,
): Promise<string> {
  const host = safeTxServiceHost(chainId)
  if (!host) {
    throw new Error(`Safe Transaction Service not available for chain ${chainId}`)
  }
  const startedAt = Date.now()
  let consecutiveMisses = 0
  while (Date.now() - startedAt < budgetMs) {
    try {
      const res = await fetch(
        `https://${host}/api/v1/multisig-transactions/${safeTxHash}/`,
      )
      if (res.ok) {
        const data = await res.json()
        if (typeof data.transactionHash === 'string' && data.transactionHash.startsWith('0x')) {
          return data.transactionHash
        }
        consecutiveMisses = 0
      } else if (res.status === 404 || res.status === 422) {
        consecutiveMisses++
        if (consecutiveMisses >= 10) {
          throw new Error(
            'Transaction not found in Safe Transaction Service — your wallet may not be a Safe, or the transaction has not been broadcast yet.',
          )
        }
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes('not found in Safe')) throw err
      // Network blip — keep polling
    }
    await new Promise(r => setTimeout(r, 5_000))
  }
  throw new Error(
    'Safe transaction timed out — please complete the signing in your Safe and click Retry verification with the onchain tx hash.',
  )
}

/** Poll Safe Messages Service for the assembled ERC-1271-compatible
 *  signature. Multi-sig Safes return a 32-byte safeMessageHash (66 chars
 *  including 0x) instead of a sig when asked to `personal_sign` /
 *  `eth_signTypedData_v4`; we substitute the real `preparedSignature`
 *  here so the backend's ERC-1271 verification path works. */
export async function pollSafeMessagesService(
  chainId: number | undefined,
  safeAddress: string,
  safeMessageHash: string,
  budgetMs = 30 * 60_000,
): Promise<string> {
  const host = safeTxServiceHost(chainId)
  if (!host) {
    throw new Error(`Safe Transaction Service not available for chain ${chainId}`)
  }
  const startedAt = Date.now()
  while (Date.now() - startedAt < budgetMs) {
    try {
      const res = await fetch(
        `https://${host}/api/v1/safes/${safeAddress}/messages/${safeMessageHash}/`,
      )
      if (res.ok) {
        const data = await res.json()
        if (typeof data.preparedSignature === 'string' && data.preparedSignature.startsWith('0x')) {
          return data.preparedSignature
        }
      }
    } catch {
      // Network blip — keep polling
    }
    await new Promise(r => setTimeout(r, 15_000))
  }
  throw new Error(
    'Safe message timed out — please ensure all required signers have signed in their Safe and try again.',
  )
}

/** Returns true when `signature` looks like a bare safeMessageHash
 *  (32 bytes / 66 chars including 0x) instead of an actual signature. A
 *  real ECDSA sig is 65 bytes (132 chars + 0x); ERC-1271 sigs are even
 *  longer. Anything shorter than ~100 chars is either a hash or junk. */
export function looksLikeSafeMessageHash(signature: string): boolean {
  return signature.length === 66 && signature.startsWith('0x')
}
