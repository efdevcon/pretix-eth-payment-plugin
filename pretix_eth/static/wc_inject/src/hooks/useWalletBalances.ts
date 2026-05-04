import { useQuery } from '@tanstack/react-query'
import type { WCConfig } from '../config'

/** Plugin-side balance entry (matches `balances.fetch_balances_for_wallet`). */
export interface BalanceEntry {
  chain_id: number
  symbol: string
  /** Raw on-chain base units (string to preserve precision past 2^53). */
  balance: string
  decimals: number
  /** ERC-20 contract address; null for native ETH. */
  token_address: string | null
}

export interface WalletBalancesResponse {
  wallet: string
  balances: BalanceEntry[]
}

function parseOrgAndEvent(): { organizer: string; event: string } {
  const match = window.location.pathname.match(/^\/([^/]+)\/([^/]+)/)
  if (!match) throw new Error('Could not parse organizer/event from URL')
  return { organizer: match[1], event: match[2] }
}

/** Fetches per-(chain, token) balances for the connected wallet from the
 *  plugin's `/plugin/wc/wallet-balances/` endpoint. The plugin tries Zapper
 *  first and falls back to RPC if Zapper fails — same engine x402 uses.
 *  Returns an empty `balances` list if the wallet isn't connected. */
export function useWalletBalances(config: WCConfig, wallet: string | undefined) {
  return useQuery<WalletBalancesResponse>({
    queryKey: ['wc-wallet-balances', config.orderCode, wallet],
    enabled: !!wallet,
    queryFn: async () => {
      const { organizer, event } = parseOrgAndEvent()
      const url = new URL(`${config.urlPrefix}/wallet-balances/`, window.location.origin)
      url.searchParams.set('organizer', organizer)
      url.searchParams.set('event', event)
      url.searchParams.set('wallet', wallet!)
      const r = await fetch(url.toString(), { credentials: 'same-origin' })
      if (!r.ok) {
        throw new Error(`wallet-balances HTTP ${r.status}`)
      }
      return r.json()
    },
    // Balances change when the wallet sends/receives — refetch on focus + every minute.
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })
}

/** Format raw base units to a short display string (≤6 sig digits). */
export function formatBalance(raw: string, decimals: number): string {
  try {
    const n = BigInt(raw)
    if (n === BigInt(0)) return '0'
    const base = BigInt('1' + '0'.repeat(decimals))
    const whole = n / base
    const frac = n % base
    if (frac === BigInt(0)) return whole.toString()
    // Trim trailing zeros and limit to 6 significant fractional digits.
    let fracStr = frac.toString().padStart(decimals, '0').replace(/0+$/, '')
    if (whole === BigInt(0) && fracStr.length > 6) {
      // Sub-unit balance (e.g. small ETH) — keep first 6 non-zero digits.
      fracStr = fracStr.slice(0, 6)
    } else if (fracStr.length > 4) {
      fracStr = fracStr.slice(0, 4)
    }
    return fracStr ? `${whole}.${fracStr}` : whole.toString()
  } catch {
    return raw
  }
}

/** Look up the balance for a given (chain, symbol) from the response.
 *  Returns null if not found. */
export function findBalance(
  res: WalletBalancesResponse | undefined,
  chainId: number,
  symbol: string,
): BalanceEntry | null {
  if (!res) return null
  return res.balances.find(b => b.chain_id === chainId && b.symbol === symbol) ?? null
}
