import { arbitrum, arbitrumGoerli, mainnet, goerli, optimism, optimismGoerli, sepolia, zkSync } from "@wagmi/core/chains";

// Safe is only supported on certain networks there doesn't seem to be any smart way to detect if a network is supported (it doesn't follow https://github.com/ethereum-lists/chains ?), so this has to be manually configured
// Safe documentation: https://github.com/safe-global/safe-docs/blob/main/learn/safe-core/safe-core-api/available-services.md
export default [
  {
    safeNetworkIdentifier: 'mainnet',
    chain: mainnet
  },
  {
    safeNetworkIdentifier: 'goerli',
    chain: goerli
  },
  {
    safeNetworkIdentifier: 'arbitrum',
    chain: arbitrum
  },
  {
    chain: arbitrumGoerli
  },
  {
    safeNetworkIdentifier: 'optimism',
    chain: optimism
  },
  {
    chain: optimismGoerli
  },
  {
    chain: zkSync
  },
  {
    chain: sepolia
  },
];