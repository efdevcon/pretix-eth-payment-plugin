"use strict";

import { configureChains, createClient, watchAccount, watchNetwork, getProvider } from "@wagmi/core";
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

    const desiredChainID = GlobalPretixEthState.elements.buttonConnect.getAttribute("data-chain-id");
    const walletConnectProjectId = document.getElementById('web3modal').getAttribute('data-walletconnect-id');

    const chains = [
        arbitrum,
        arbitrumGoerli,
        mainnet,
        goerli,
        optimism,
        optimismGoerli,
        zkSync,
        sepolia
    ].filter(chain => chain.id === parseInt(desiredChainID));

    const { provider } = configureChains(chains, [
        walletConnectProvider({
            projectId: walletConnectProjectId,
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
        { projectId: walletConnectProjectId },
        ethereumClient
    );

    // Switch to user chosen chain before showing modal
    const desiredChain = chains.find(chain => chain.id === parseInt(desiredChainID));

    if (desiredChain) {
        GlobalPretixEthState.web3Modal.setSelectedChain(desiredChain);
    }

    let lastAccountStatus = null;

    watchAccount(async (accountState) => {
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

    GlobalPretixEthState.elements.buttonConnect.addEventListener(
        "click",
        async () => {
            try {
                // If user is already logged in we call makePayment, otherwise signIn will open the walletconnect modal, and makePayment will instead be called when the user connects
                const alreadySignedIn = await signIn();

                if (alreadySignedIn) {
                    await makePayment();
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
