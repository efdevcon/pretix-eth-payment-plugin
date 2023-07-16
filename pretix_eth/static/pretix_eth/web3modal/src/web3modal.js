"use strict";

import { configureChains, createConfig, watchAccount, watchNetwork } from "@wagmi/core";
import { EthereumClient, w3mConnectors, w3mProvider } from '@web3modal/ethereum'
import { Web3Modal } from "@web3modal/html";
import { showError, GlobalPretixEthState, signIn, displayOnlyId, getCookie } from './interface.js';
import { makePayment } from './core.js';
import chains from "./chains.js";

async function init() {
    const desiredChainID = GlobalPretixEthState.elements.buttonConnect.getAttribute("data-chain-id");
    const walletConnectProjectId = document.getElementById('web3modal').getAttribute('data-walletconnect-id');

    // Some wallets read the page title and presents it to the user in the wallet - the pretix generated one looks confusing, so we override it before instantiating web3modal
    document.title = 'Pretix Payment';

    const desiredChain = chains.filter(chainInfo => chainInfo.chain.id === parseInt(desiredChainID));

    if (desiredChain.length < 1) {
        showError('Invalid chain ID');

        return;
    }

    const { publicClient } = configureChains([desiredChain[0].chain], [w3mProvider({ projectId: walletConnectProjectId })])

    console.log(chains, 'chains')

    const wagmiClient = createConfig({
        autoConnect: true,
        connectors: [
            ...w3mConnectors({
                projectId:
                    walletConnectProjectId,
                version: 2,
                chains: [desiredChain[0].chain]
            })
        ],
        publicClient,
    });

    // Web3Modal and Ethereum Client
    const ethereumClient = new EthereumClient(wagmiClient, desiredChain);
    GlobalPretixEthState.web3Modal = new Web3Modal(
        { projectId: walletConnectProjectId },
        ethereumClient
    );
    GlobalPretixEthState.safeNetworkIdentifier = desiredChain[0].safeNetworkIdentifier;

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

    GlobalPretixEthState.elements.divPrepare.style.display = "block";
    document.getElementById('spinner').style.display = 'none';

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

init();