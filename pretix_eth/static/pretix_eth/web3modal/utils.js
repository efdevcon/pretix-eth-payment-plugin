"use strict";

const GlobalPretixEthState = {
    selectedAccount: null,  // address of the currently connected account
    signedByAccount: null,  // address of the account that has signed the message, to check on account chages
    messageSignature: null,
    paymentDetails: null,
    // payment flow flags
    signatureRequested: false,  // true if js has
    transactionRequested: false,
    transactionHashSubmitted: false,
    lastOrderStatus: '',
    elements: {
        divPrepare: document.getElementById("prepare"),
        divError: document.getElementById("message-error"),
        divSuccess: document.getElementById("success"),
        divTransactionHash: document.getElementById("pretix-eth-transaction-hash"),
        aOrderDetailURL: document.getElementById("pretix-order-detail-url"),
        buttonConnect: document.getElementById("btn-connect")
    },
    selectors: {
        paymentSteps: document.querySelectorAll(".pretix-eth-payment-steps")
    }
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

export {getCookie, GlobalPretixEthState}