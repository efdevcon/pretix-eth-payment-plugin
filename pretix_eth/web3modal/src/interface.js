"use strict";

import { getAccount } from "@wagmi/core";
import chains from "./chains.js";

// files that interact with the page DOM

const GlobalPretixEthState = {
    selectedAccount: null,  // address of the currently connected account
    signedByAccount: null,  // address of the account that has signed the message, to check on account chages
    messageSignature: null,
    paymentDetails: null,
    // payment flow flags
    signatureRequested: false,  // true if js has
    transactionRequested: false,
    transactionHashSubmitted: false,
    //
    lastOrderStatus: '',
    // interface and data-bearing tags
    elements: {
        divPrepare: document.getElementById("prepare"),
        divError: document.getElementById("message-error"),
        divSuccess: document.getElementById("success"),
        divTransactionHash: document.getElementById("pretix-eth-transaction-hash"),
        aOrderDetailURL: document.getElementById("pretix-order-detail-url"),
        aNetworkData: document.getElementById("pretix-data-chain-info"),
        buttonConnect: document.getElementById("btn-connect"),
        submittedTransactionHash: document.getElementById("pretix-eth-submitted-transaction-hash"),
        paymentNetworkName: document.getElementById("payment-network-id")

    },
    selectors: {
        paymentSteps: document.querySelectorAll(".pretix-eth-payment-steps")
    },
    // json data used to find block explorere urls mostly
    chains: [],
    // web3modal instance
    web3Modal: null
}

async function signIn() {
    try {
        const account = await getAccount();

        if (account.isConnected) {
            return true;
        }

        await GlobalPretixEthState.web3Modal.open()
    } catch (e) {
        console.error(e, 'Sign in failed')

        throw e;
    }

    return false;
}


function getTransactionDetailsURL() {
    return GlobalPretixEthState.elements.buttonConnect.getAttribute("data-transaction-details-url");
}

async function getPaymentTransactionData(refresh = false) {
    if (!refresh && GlobalPretixEthState.paymentDetails !== null) {
        return GlobalPretixEthState.paymentDetails
    }

    const walletAddress = await getAccount()?.address;
    const url = getTransactionDetailsURL();
    const response = await fetch(url + '?' + new URLSearchParams({
        sender_address: walletAddress
    }));

    if (response.status >= 400) {
        throw "Failed to fetch order details. If this problem persists, please contact the organizer directly.";
    }

    return await response.json();
}

function getCookie(name) {
    // Add the = sign
    name = name + '=';

    // Get the decoded cookie
    const decodedCookie = decodeURIComponent(document.cookie);

    // Get all cookies, split on ; sign
    const cookies = decodedCookie.split(';');

    // Loop over the cookies
    for (let i = 0; i < cookies.length; i++) {
        // Define the single cookie, and remove whitespace
        const cookie = cookies[i].trim();

        // If this cookie has the name of what we are searching
        if (cookie.indexOf(name) == 0) {
            // Return everything after the cookies name
            return cookie.substring(name.length, cookie.length);
        }
    }
}

function convertHashToExplorerLink(chain_id, transactionHash) {
    const chainMatch = chains.filter(chainInfo => chainInfo.chain.id === parseInt(chain_id));
    let chain;

    if (chainMatch) chain = chainMatch[0].chain;

    const explorerURL = chain?.blockExplorers?.etherscan?.url;

    if (explorerURL) {
        return '<a href="' + explorerURL + '/tx/' + transactionHash + '" target="_blank">' + transactionHash + "</a>"
    } else {
        return transactionHash
    }
}

/*
* Success and error handling
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
            if (message.data && message.data.message) {
                message = message.data.message + ". Please try again."
            } else if (message.message !== undefined) {
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
        function (div) {
            if (div.id === divId) {
                div.style.display = "block";
            } else {
                div.style.display = "none";
            }
        }
    );
}

function showSuccessMessage(transactionHash, safeUrl) {
    GlobalPretixEthState.transactionHashSubmitted = true;
    const chain_id = GlobalPretixEthState.elements.aNetworkData.getAttribute("data-chain-id")
    if (safeUrl) {
        GlobalPretixEthState.elements.divTransactionHash.innerHTML = safeUrl
    } else {
        GlobalPretixEthState.elements.divTransactionHash.innerHTML = convertHashToExplorerLink(chain_id, transactionHash);
    }
    displayOnlyId();
    GlobalPretixEthState.elements.divSuccess.style.display = "block";
}

export {
    getCookie, GlobalPretixEthState,
    getPaymentTransactionData,
    convertHashToExplorerLink,
    getTransactionDetailsURL,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage,
    signIn
};
