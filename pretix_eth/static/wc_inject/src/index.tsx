import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WagmiProvider } from 'wagmi'
import { readConfig, initAppKit, setAppKitInstance } from './config'
import { WCPaymentApp } from './WCPaymentApp'

const config = readConfig()
const { wagmiAdapter, appKit } = initAppKit(config.wcProjectId, {
  safePaymentsEnabled: config.safePaymentsEnabled,
})
setAppKitInstance(appKit)
const queryClient = new QueryClient()

// Expose the plugin version as a global so anyone debugging can type
// `WC_INJECT_VERSION` in the console without digging through React state.
// Also one-shot log it for the timeline above any handlePay activity.
if (typeof window !== 'undefined') {
  ;(window as unknown as { WC_INJECT_VERSION?: string }).WC_INJECT_VERSION = config.pluginVersion
  // eslint-disable-next-line no-console
  console.info(`[wc_inject] boot { pluginVersion: "${config.pluginVersion ?? 'unknown'}" }`)
}

const el = document.getElementById('wc-payment-root')
if (el) {
  createRoot(el).render(
    <WagmiProvider config={wagmiAdapter.wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <WCPaymentApp config={config} />
      </QueryClientProvider>
    </WagmiProvider>
  )
  // The Django template ships a sibling `#wc-boot-loading` div so the user
  // sees branded "Pay with ETH / Loading wallet…" copy immediately, before the
  // bundle finishes downloading on slow connections. Remove it from the DOM
  // once React has mounted so it cannot reappear during stage transitions.
  document.getElementById('wc-boot-loading')?.remove()
  // Mark this session as "bundle has booted" so any subsequent Pretix
  // re-render of the checkout template (which re-includes the boot loader
  // markup) hides it via the inline CSS rule keyed off
  // `html.wc-inject-booted`. Avoids the placeholder flashing during
  // disconnect when Pretix partially re-renders the payment step.
  try {
    sessionStorage.setItem('wc-inject-booted', '1')
    document.documentElement.classList.add('wc-inject-booted')
  } catch (_) { /* sessionStorage unavailable — fall back to normal flow */ }
} else {
  console.error('wc-payment-root element missing')
}
