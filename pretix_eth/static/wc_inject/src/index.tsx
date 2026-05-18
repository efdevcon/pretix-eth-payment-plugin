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
  // Boot-loader removal happens in WCPaymentApp's mount effect — moved
  // out of here because `createRoot.render()` only SCHEDULES React's
  // reconciliation, it doesn't paint synchronously. Removing the boot
  // loader on the same tick left a brief empty frame on slow connections
  // where the bundle had parsed but React hadn't painted yet.
} else {
  console.error('wc-payment-root element missing')
}
