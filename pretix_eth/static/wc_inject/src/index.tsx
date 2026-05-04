import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WagmiProvider } from 'wagmi'
import { readConfig, initAppKit, setAppKitInstance } from './config'
import { WCPaymentApp } from './WCPaymentApp'

const config = readConfig()
const { wagmiAdapter, appKit } = initAppKit(config.wcProjectId)
setAppKitInstance(appKit)
const queryClient = new QueryClient()

const el = document.getElementById('wc-payment-root')
if (el) {
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
