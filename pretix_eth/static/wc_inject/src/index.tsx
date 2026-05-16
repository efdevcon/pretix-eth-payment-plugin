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
  // The Django template ships a static loading placeholder inside this div so
  // the user sees branded "Pay with ETH / Loading wallet…" copy immediately
  // (before the 5.5 MB bundle finishes downloading on slow connections). Clear
  // it explicitly before mounting React — createRoot does this on its own but
  // emits a dev-mode warning when the container has non-React children, and
  // doing it manually avoids any future React-version edge cases.
  el.innerHTML = ''
  createRoot(el).render(
    <WagmiProvider config={wagmiAdapter.wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <WCPaymentApp config={config} />
      </QueryClientProvider>
    </WagmiProvider>
  )
} else {
  console.error('wc-payment-root element missing')
}
