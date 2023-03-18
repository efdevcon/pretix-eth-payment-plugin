"use strict";

import { configureChains, createClient, watchAccount, watchNetwork } from "@wagmi/core";
import { EthereumClient, w3mConnectors, w3mProvider } from '@web3modal/ethereum'
import { arbitrum, arbitrumGoerli, mainnet, goerli, optimism, optimismGoerli, sepolia, zkSync } from "@wagmi/core/chains";
import { Web3Modal } from "@web3modal/html";
import { showError, GlobalPretixEthState, signIn, displayOnlyId } from './interface.js';
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

    const { provider } = configureChains(chains, [w3mProvider({ projectId: walletConnectProjectId })])

    const wagmiClient = createClient({
        autoConnect: true,
        connectors: [...w3mConnectors({ projectId: walletConnectProjectId, version: 2, chains })],
        provider,
    });

    // Web3Modal and Ethereum Client
    const ethereumClient = new EthereumClient(wagmiClient, chains);

    GlobalPretixEthState.web3Modal = new Web3Modal(
        { projectId: walletConnectProjectId },
        ethereumClient
    );

    let lastAccountStatus;

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

    // Clear any errors/statuses upon switching chain
    watchNetwork(() => {
        displayOnlyId('prepare');
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
