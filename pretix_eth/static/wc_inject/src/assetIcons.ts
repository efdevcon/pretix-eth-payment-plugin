// Network + token logos for the in-checkout payment picker.
//
// PNGs live under pretix_eth/static/wc_inject/icons/ and are downloaded from
// Zapper's public asset bucket (same source the devcon admin + custom
// checkout use) at build time. Served by Pretix at /static/wc_inject/icons/…
// via Django's staticfiles.
//
// We reference them by URL rather than inlining because (a) they're PNGs
// (inlining defeats browser cache), (b) they're small enough that the extra
// HTTP hit is cheap, and (c) asset URLs can be CDN-swapped without a
// code change later if we self-host elsewhere.

const URL_PREFIX = '/static/wc_inject/icons'

export const NETWORK_LOGOS: Record<number, string> = {
  1: `${URL_PREFIX}/networks/ethereum.png`,
  10: `${URL_PREFIX}/networks/optimism.png`,
  137: `${URL_PREFIX}/networks/polygon.png`,
  8453: `${URL_PREFIX}/networks/base.png`,
  42161: `${URL_PREFIX}/networks/arbitrum.png`,
}

export const TOKEN_LOGOS: Record<string, string> = {
  USDC: `${URL_PREFIX}/tokens/usdc.png`,
  USDT0: `${URL_PREFIX}/tokens/usdt0.png`,
  ETH: `${URL_PREFIX}/tokens/eth.png`,
}
