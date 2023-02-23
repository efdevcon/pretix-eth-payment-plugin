import { signTypedData, erc20ABI, configureChains, createClient, getAccount, watchAccount, watchNetwork, getNetwork, switchNetwork, signMessage, sendTransaction, prepareSendTransaction, readContract, prepareWriteContract, writeContract } from "@wagmi/core";

import { arbitrum, arbitrumGoerli, mainnet, goerli, optimism, optimismGoerli, sepolia, zkSync } from "@wagmi/core/chains";

import { Web3Modal } from "@web3modal/html";

import { ethers } from "ethers";

import {
  EthereumClient,
  modalConnectors,
  walletConnectProvider,
} from "@web3modal/ethereum";

window.__web3modal = {
  ethers: {
    parseEther: ethers.utils.parseEther
  },
  wagmi: {
    core: {
      signTypedData,
      erc20ABI,
      configureChains,
      writeContract,
      prepareWriteContract,
      createClient,
      getAccount,
      watchAccount,
      watchNetwork,
      getNetwork,
      switchNetwork,
      signMessage,
      sendTransaction,
      prepareSendTransaction,
      readContract
    },
    chains: {
      arbitrum,
      arbitrumGoerli,
      mainnet,
      sepolia,
      goerli,
      optimism,
      optimismGoerli,
      zkSync
    }
  },
  web3modal: {
    ethereum: {
      EthereumClient,
      modalConnectors,
      walletConnectProvider,
    },
    html: {
      Web3Modal
    }
  },
}