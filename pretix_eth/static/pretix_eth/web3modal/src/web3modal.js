"use strict";

import { configureChains, createClient, watchAccount, watchNetwork } from "@wagmi/core";
import { arbitrum, arbitrumGoerli, mainnet, goerli, optimism, optimismGoerli, sepolia, zkSync } from "@wagmi/core/chains";
import { Web3Modal } from "@web3modal/html";
import {
    EthereumClient,
    modalConnectors,
    walletConnectProvider,
} from "@web3modal/ethereum";
import { showError, GlobalPretixEthState, signIn } from './interface.js';
import { makePayment } from './core.js';

async function init() {
    GlobalPretixEthState.elements.divPrepare.style.display = "block";

    const chains = [
        arbitrum,
        arbitrumGoerli,
        mainnet,
        goerli,
        optimism,
        optimismGoerli,
        zkSync,
        sepolia
    ];

    // Wagmi Core Client
    const { provider } = configureChains(chains, [
        walletConnectProvider({
            projectId: "c1b5ad74fb26a47cd04679fb8044eff0",
            version: 2,
            chains
        }),
    ]);

    const wagmiClient = createClient({
        autoConnect: true,
        connectors: modalConnectors({ appName: "web3Modal", chains }),
        provider,
    });

    // Web3Modal and Ethereum Client
    const ethereumClient = new EthereumClient(wagmiClient, chains);

    GlobalPretixEthState.web3Modal = new Web3Modal(
        { projectId: "c1b5ad74fb26a47cd04679fb8044eff0" },
        ethereumClient
    );

    // Switch to user chosen chain before showing modal
    const desiredChainID = GlobalPretixEthState.elements.buttonConnect.getAttribute("data-chain-id");
    const desiredChain = chains.find(chain => chain.id === parseInt(desiredChainID));

    if (desiredChain) {
        GlobalPretixEthState.web3Modal.setSelectedChain(desiredChain);
    }

    let lastAccountStatus = null;

    watchAccount(async (accountState) => {
        // Reload if user disconnects
        if (lastAccountStatus === 'connected' && accountState.status === 'disconnected') {
            location.reload();
        }

        // Detect when sign-in is succesful and automatically proceed to makePayment
        if (lastAccountStatus === 'connecting' && accountState.status === 'connected') {
            try {
                await makePayment();
            } catch (error) {
                showError(error)
            }
        }

        lastAccountStatus = accountState.status;
    });

    let lastNetwork = null;

    watchNetwork(async (network) => {
        // Whenever user switches network, call makePayment again
        if (lastNetwork !== null) {
            try {
                await makePayment();
            } catch (error) {
                showError(error)
            }
        }

        lastNetwork = network?.chain.id;
    });

    GlobalPretixEthState.elements.buttonConnect.addEventListener(
        "click",
        async () => {
            try {
                // If user refreshes the page after signing in, the user will still be logged in - we then call makePayment directly
                const alreadySignedIn = await signIn();

                if (alreadySignedIn) {
                    // Sign out
                    makePayment();
                }
            } catch (e) {
                showError(error)
            }
        }
    );
}

window.addEventListener('load', async () => {
    await init();
});
