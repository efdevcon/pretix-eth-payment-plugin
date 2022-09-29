"use strict";

import {showError, GlobalPretixEthState, loadChainsJSON} from './interface.js';
import {makePayment} from './core.js';

// Imports
const Web3Modal = window.Web3Modal.default;

async function init() {
    GlobalPretixEthState.elements.divPrepare.style.display = "block";

    loadChainsJSON();
    GlobalPretixEthState.web3Modal = new Web3Modal({
        cacheProvider: false
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
