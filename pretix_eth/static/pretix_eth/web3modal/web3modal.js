"use strict";

import {showError} from './interface.js';
import {makePayment} from './core.js';
import {GlobalPretixEthState} from './utils.js';

async function init() {
    GlobalPretixEthState.elements.divPrepare.style.display = "block";

    const providerOptions = {
        walletconnect: {
            package: WalletConnectProvider,
            options: {
                infuraId: "INFURA_ID" // todo required, make it an endpoint
            }
        }
    };
    web3Modal = new Web3Modal({
        cacheProvider: false,
        providerOptions
    });
    GlobalPretixEthState.elements.buttonConnect.addEventListener(
        "click",
        web3ModalOnConnect
    );
}

/**
 * Connect wallet button pressed.
 */
async function web3ModalOnConnect() {
    try {
        await makePayment();
    } catch (error) {
        showError(error)
    }
}

window.addEventListener('load', async () => {
    await init();
});
