"use strict";

// files that interact with the page DOM

import {GlobalPretixEthState} from './utils.js';


async function initWeb3() {
    let provider;
    try {
        provider = await web3Modal.connect();
    } catch(e) {
        showError("Failed to connect to a wallet provider.");
    }
    window.web3 = new Web3(provider);

    // Subscribe to accounts change
    provider.on("accountsChanged", (accounts) => {
        location.reload();
    });

    // Subscribe to chainId change
    provider.on("chainChanged", (chainId) => {
        location.reload();
    });

    // Subscribe to networkId change
    provider.on("networkChanged", (networkId) => {
        location.reload();
    });

    return provider
}


async function getAccount() {
    if (window.web3 === undefined || window.web3.eth === undefined) {
        await initWeb3();
    }
    // Get a Web3 instance for the wallet
    const accounts = await window.web3.eth.getAccounts();
    // MetaMask does not give you all accounts, only the selected account
    return accounts[0];
}


function getTransactionDetailsURL() {
    return GlobalPretixEthState.elements.buttonConnect.getAttribute("data-transaction-details-url");
}


async function getERC20ABI() {
    let url = GlobalPretixEthState.elements.buttonConnect.getAttribute("data-erc20-abi-url");
    let response = await fetch(url);
    if (response.ok) {
        return response.json()
    } else {
        showError("Failed to fetch ERC20 ABI.")
    }
}


async function getPaymentTransactionData(refresh = false){
    if (!refresh && GlobalPretixEthState.paymentDetails !== null) {
        return GlobalPretixEthState.paymentDetails
    }
    let walletAddress = await getAccount();
    const url = getTransactionDetailsURL();
    const response = await fetch(url + '?' + new URLSearchParams({
        sender_address: walletAddress
    }));
    if (response.status >= 400) {
        throw "Failed to fetch order details. If this problem persists, please contact the organizer directly.";
    }
    return await response.json();
}


async function periodicCheck() {
    let url = GlobalPretixEthState.elements.aOrderDetailURL.getAttribute("data-order-detail-url");
    let response = await fetch(url);
    if (response.ok) {
        let data = await response.json()
        if (GlobalPretixEthState.lastOrderStatus === '') {
            GlobalPretixEthState.lastOrderStatus = data.status;
        } else if (GlobalPretixEthState.lastOrderStatus !== data.status) {
            // status has changed to PAID
            if (data.status === 'p') {
                location.reload();
            }
        }
    }
}

async function runPeriodicCheck() {
  while (true) {
    await periodicCheck();
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}


/*
* Success and error handdling
*/

function showError(message = '', reset_state = true) {
    if (GlobalPretixEthState.transactionHashSubmitted) {
        // do not display errors or reset state after the transaction hash has been successfully submitted to the BE
        message = "";
        reset_state = false;
    } else {
        // reset
        GlobalPretixEthState.transactionRequested = false;
        GlobalPretixEthState.signatureRequested = false;

        if (typeof message === "object") {
            if (message.message !== undefined) {
                message = message.message + ". Please try again."
            } else if (message.error !== undefined && message.error.message !== undefined) {
                message = message.error.message + ". Please try again.";
            } else {
                message = "";
            }
        }
        if (message === "") {
            message = "There was an error, please try again, or contact support if you have already confirmed a payment in your wallet provider."
        }
    }

    GlobalPretixEthState.elements.divError.innerHTML = message;
    if (reset_state === true) {
        displayOnlyId("prepare");
    }
    try {
        GlobalPretixEthState.elements.buttonConnect.removeAttribute("disabled");
    } catch (e) {
        return false
    }

    return false
}


function resetErrorMessage() {
    GlobalPretixEthState.elements.divError.innerHTML = '';
}


function displayOnlyId(divId) {
    GlobalPretixEthState.selectors.paymentSteps.forEach(
        function(div) {
            if (div.id === divId) {
                div.style.display = "block";
            } else {
                div.style.display = "none";
            }
        }
    );
}


function showSuccessMessage(transactionHash) {
    GlobalPretixEthState.transactionHashSubmitted = true;
    GlobalPretixEthState.elements.divTransactionHash.innerText = transactionHash;
    displayOnlyId();
    GlobalPretixEthState.elements.divSuccess.style.display = "block";
}

export {
    getTransactionDetailsURL, getERC20ABI,
    getPaymentTransactionData, runPeriodicCheck,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage, getAccount, initWeb3
};
