'use client'

import React from 'react'
import { DaimoPayProvider, getDefaultConfig } from '@daimo/pay'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WagmiProvider, createConfig } from 'wagmi'

const config = createConfig(
  getDefaultConfig({
    appName: 'Daimo Pay',
  }),
)

const queryClient = new QueryClient()

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <DaimoPayProvider>{children}</DaimoPayProvider>
      </QueryClientProvider>
    </WagmiProvider>
  )
}
