// AppKit + wagmi setup. Reads config from a <script id="wc-config"> JSON tag
// injected by the Pretix checkout template.
import { createAppKit } from '@reown/appkit/react'
import { WagmiAdapter } from '@reown/appkit-adapter-wagmi'
import { mainnet, optimism, polygon, base, arbitrum } from '@reown/appkit/networks'
import type { AppKitNetwork } from '@reown/appkit/networks'

export interface WCConfig {
  wcProjectId: string
  orderCode: string
  orderSecret: string
  /** Pretix order total in USD as a decimal string ("12.34"). Used by the
   *  asset/network picker to compute insufficient-balance gating against the
   *  wallet balances returned from /plugin/wc/wallet-balances/. May be empty
   *  if the template rendered the page without the field (older deploys). */
  orderTotalUsd?: string
  /** Buyer's email from the Pretix Order. Pre-filled into the support-email
   *  body so the buyer doesn't have to retype it. Empty when the order has
   *  no email recorded (rare). */
  buyerEmail?: string
  urlPrefix: string
  csrfToken: string
  /** Optional support email set in the plugin admin. Shown in a fallback
   *  contact block if the buyer's payment gets stuck; empty string hides it. */
  supportEmail?: string
  /** Optional FE-domain URL template (same setting that overrides the email
   *  `{url}` placeholder). When set, SuccessStep redirects to the FE order
   *  page instead of Pretix's native one — keeps the post-payment landing
   *  consistent with the confirmation email. Supports `{code}` and
   *  `{secret}` substitution. Empty string = fall back to Pretix's order. */
  frontendOrderUrlTemplate?: string
  /** True when this event has only ETH-on-mainnet enabled (the wave-launch
   *  flow). Drives the ConnectStep heading copy. */
  ethMainnetOnly?: boolean
  /** Plugin version (`pretix_eth/__init__.py:__version__`). Surfaced via
   *  WCConfig so debug logs and the in-page footer don't need a separate
   *  injection path. */
  pluginVersion?: string
}

export function readConfig(): WCConfig {
  const el = document.getElementById('wc-config')
  if (!el) throw new Error('wc-config script tag missing from template')
  return JSON.parse(el.textContent || '{}') as WCConfig
}

const NETWORKS: [AppKitNetwork, ...AppKitNetwork[]] = [
  mainnet, optimism, polygon, base, arbitrum,
]

// Wallets pinned to the top of the AppKit picker. Mirrors devcon's
// src/context/appkit-config.ts so the same shortlist appears across surfaces.
// IDs come from cloud.reown.com's wallet directory.
const FEATURED_WALLET_IDS = [
  'ecc4036f814562b41a5268adc86270fba1365471402006302e70169465b7ac18', // Zerion
  '1ae92b26df02f0abca6304df07debccd18262fdf5fe82daa81593582dac9a369', // Rainbow
  'fd20dc426fb37566d803205b19bbc1d4096b248ac04548e3cfb6b3a38bd033aa', // Coinbase
  'c57ca95b47569778a828d19178114f4db188b89b763c899ba0be274e97267d96', // MetaMask
]

// Wallets explicitly hidden from the AppKit picker. Safes are excluded here
// because the wc_inject flow doesn't bridge through Safe Tx Service / Safe
// Messages API to recover the on-chain hash for multisigs (the devcon-next
// FE does, but this legacy bundle hasn't been upgraded). A buyer who paid
// with a Safe would see the tx confirm on-chain but the page never
// recover — leaving the order stuck. Hide the option until that path is
// implemented; admin manual-verify remains the recovery channel.
const EXCLUDED_WALLET_IDS = [
  '225affb176778569276e484e1b92637ad061b01e13a048b35a9d280c3b58970f', // Safe
]

export function initAppKit(projectId: string) {
  const wagmiAdapter = new WagmiAdapter({
    projectId,
    networks: NETWORKS,
  })

  const appKit = createAppKit({
    adapters: [wagmiAdapter],
    networks: NETWORKS,
    projectId,
    metadata: {
      name: 'Pretix crypto payment',
      description: 'Pay for your ticket with crypto',
      url: typeof window !== 'undefined' ? window.location.origin : '',
      icons: [],
    },
    features: {
      analytics: false,
      email: false,
      socials: [],
    },
    featuredWalletIds: FEATURED_WALLET_IDS,
    excludeWalletIds: EXCLUDED_WALLET_IDS,
  })

  return { wagmiAdapter, appKit, open: () => appKit.open() }
}

// Module-level singleton — set by index.tsx, used by components
export let appKitInstance: ReturnType<typeof createAppKit> | null = null

export function setAppKitInstance(ak: ReturnType<typeof createAppKit>) {
  appKitInstance = ak
}
