import { useQuery } from '@tanstack/react-query'
import type { WCConfig } from '../config'

export interface PaymentOption {
  chain_id: number
  chain_name: string
  symbol: string
}

export interface PaymentOptionsResponse {
  options: PaymentOption[]
  eth_available: boolean
  eth_disabled_reason: string | null
  /** Live ETH price in USD from the plugin's dual-oracle fetch (Coinbase +
   *  Binance). Same value the quote-creation endpoint uses, so the picker's
   *  "balance is enough" check matches what the server will accept at quote
   *  time. `null` when ETH is disabled (oracles diverged or unreachable). */
  eth_price_usd: number | null
  receive_address: string
  chain_metadata: Record<string, { name: string; explorer_url: string }>
}

function parseOrgAndEvent(): { organizer: string; event: string } {
  // Pretix checkout URLs: /{organizer}/{event}/... or /{organizer}/{event}/checkout/...
  const match = window.location.pathname.match(/^\/([^/]+)\/([^/]+)/)
  if (!match) throw new Error('Could not parse organizer/event from URL')
  return { organizer: match[1], event: match[2] }
}

export function usePaymentOptions(config: WCConfig) {
  return useQuery<PaymentOptionsResponse>({
    queryKey: ['wc-payment-options', config.orderCode],
    queryFn: async () => {
      const { organizer, event } = parseOrgAndEvent()
      const url = new URL(`${config.urlPrefix}/payment-options/`, window.location.origin)
      url.searchParams.set('organizer', organizer)
      url.searchParams.set('event', event)
      // Buyer auth: the plugin validates order_code + order_secret against
      // the Order record. Both are injected into WCConfig by Pretix's
      // checkout template, so we always have them on hand.
      url.searchParams.set('order_code', config.orderCode)
      url.searchParams.set('order_secret', config.orderSecret)
      const r = await fetch(url.toString(), { credentials: 'same-origin' })
      if (!r.ok) {
        throw new Error(`payment-options HTTP ${r.status}`)
      }
      return r.json()
    },
    staleTime: 60_000, // options are stable within a session; don't refetch on focus
    retry: 1,
  })
}
