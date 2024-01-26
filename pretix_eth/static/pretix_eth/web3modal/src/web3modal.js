"use strict";

import { watchAccount, watchNetwork } from "@wagmi/core";
import { createWeb3Modal, defaultWagmiConfig } from '@web3modal/wagmi1/react'
import { showError, GlobalPretixEthState, signIn, displayOnlyId, getCookie } from './interface.js';
import { makePayment } from './core.js';
import chainsInfo from "./chains.js";

async function init() {
    const desiredChainID = GlobalPretixEthState.elements.buttonConnect.getAttribute("data-chain-id");
    const walletConnectProjectId = document.getElementById('web3modal').getAttribute('data-walletconnect-id');

    // Some wallets read the page title and presents it to the user in the wallet - the pretix generated one looks confusing, so we override it before instantiating web3modal
    document.title = 'Pretix Payment';

    const desiredChain = chainsInfo.filter(chainInfo => chainInfo.chain.id === parseInt(desiredChainID));

    if (desiredChain.length < 1) {
        showError('Invalid chain ID');

        return;
    }

    const metadata = {
        name: 'Pretix Payment Plugin',
        description: 'Pretix Payment Plugin',
        url: window.location.origin,
        icons: ['https://avatars.githubusercontent.com/u/37784886']
    }
    const chains = [desiredChain[0].chain];
    const wagmiConfig = defaultWagmiConfig({ chains, projectId: walletConnectProjectId, appName: metadata.name })

    GlobalPretixEthState.web3Modal = createWeb3Modal({
        wagmiConfig, projectId: walletConnectProjectId, chains, themeMode: 'light'
    })

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