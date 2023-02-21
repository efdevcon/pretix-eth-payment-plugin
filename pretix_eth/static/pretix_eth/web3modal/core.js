"use strict";

import {
    getTransactionDetailsURL,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage, getAccount,
    getCookie, GlobalPretixEthState, getPaymentTransactionData, getERC20ABI
} from './interface.js';
import { runPeriodicCheck } from './periodic_check.js';

/*
* Called on "Connect wallet and pay" button click and every chain/account change
*
* Step 1
*/
async function makePayment() {
    async function _checkChainAndProceed() {
        // refresh paymentDetails in case account has changed
        GlobalPretixEthState.paymentDetails = await getPaymentTransactionData(true);

        if (GlobalPretixEthState.paymentDetails['is_signature_submitted'] === true) {
            showError("It seems that you have paid for this order already.")
            return
        }

        if (GlobalPretixEthState.paymentDetails['has_other_unpaid_orders'] === true) {
            showError("Please wait for other payments from your wallet to be confirmed before submitting another transaction.")
            return
        }

        const {
            wagmi: {
                core: {
                    switchNetwork,
                    getNetwork
                },
            },
        } = window.__web3modal

        const network = await getNetwork();
        const networkIsWrong = network.chain.id !== GlobalPretixEthState.paymentDetails.chain_id

        if (networkIsWrong) {
            // Switch network is non-blocking so we can't just await it - we'll be signing on the wrong chain then
            // Instead we switch network and wait for the user to accept, and whenever the network changes we call makePayment again (happens outside this function)
            try {
                console.log('huehue')
                displayOnlyId("switching-chains");

                await switchNetwork({
                    chainId: GlobalPretixEthState.paymentDetails.chain_id,
                })
            } catch (e) {
                // showError("Please wait for other payments from your wallet to be confirmed before submitting another transaction.")

                showError(e)
            }
        } else {
            await signMessage();
        }

    }

    resetErrorMessage();

    try {
        await _checkChainAndProceed();
    } catch (error) {
        showError(error, true);
    }
}

/* Step 2 */
async function signMessage() {
    async function _signMessage() {
        GlobalPretixEthState.selectedAccount = await getAccount();
        GlobalPretixEthState.paymentDetails = await getPaymentTransactionData();

        // sign the message
        if (
            GlobalPretixEthState.messageSignature !== null
            && GlobalPretixEthState.selectedAccount === GlobalPretixEthState.signedByAccount
        ) {
            // skip the signature step if we have one already
            await submitTransaction();
        } else {
            if (!GlobalPretixEthState.signatureRequested) {
                displayOnlyId("sign-a-message");
                GlobalPretixEthState.signatureRequested = true;

                const message = GlobalPretixEthState.paymentDetails['message'];

                const signature = await window.__web3modal.wagmi.core.signTypedData({
                    domain: message.domain,
                    types: message.types,
                    value: message.message
                })

                GlobalPretixEthState.messageSignature = signature;
                GlobalPretixEthState.signedByAccount = GlobalPretixEthState.selectedAccount;

                await submitTransaction();
            } else {
                console.log("Requesting more than one message signature.");
            }
        }
    }
    try {
        await _signMessage();
    } catch (error) {
        showError(error);
        GlobalPretixEthState.signatureRequested = false;
    }
}

/* Step 3 */
async function submitTransaction() {
    async function _submitTransaction() {
        if (GlobalPretixEthState.transactionRequested === true) {
            console.log("Transaction was already submitted.");
            return
        }

        GlobalPretixEthState.transactionRequested = true
        GlobalPretixEthState.paymentDetails = await getPaymentTransactionData();

        // make the payment
        if (GlobalPretixEthState.paymentDetails['erc20_contract_address'] !== null) {
            const balance = await window.__web3modal.wagmi.core.readContract({
                abi: window.__web3modal.wagmi.core.erc20ABI,
                address: GlobalPretixEthState.paymentDetails['erc20_contract_address'],
                functionName: 'balanceOf',
                args: [GlobalPretixEthState.paymentDetails['erc20_contract_address']],
            });

            if (BigInt(balance) < BigInt(GlobalPretixEthState.paymentDetails['amount'])) {
                showError("Not enough balance to pay using this wallet, please use another currency or payment method, or transfer funds to your wallet and try again.", true);
                return
            }

            displayOnlyId("send-transaction");

            try {
                const config = await window.__web3modal.wagmi.core.prepareWriteContract({
                    address: GlobalPretixEthState.paymentDetails['erc20_contract_address'],
                    abi: window.__web3modal.wagmi.core.erc20ABI,
                    functionName: 'transfer',
                    args: [GlobalPretixEthState.paymentDetails['recipient_address'], GlobalPretixEthState.paymentDetails['amount']]
                })

                const result = await window.__web3modal.wagmi.core.writeContract(config)

                await submitSignature(result.hash);
            } catch (e) {
                showError(e);
            }
        } else { // crypto transfer
            displayOnlyId("send-transaction");

            try {
                const transactionConfig = await window.__web3modal.wagmi.core.prepareSendTransaction({
                    request: {
                        to: GlobalPretixEthState.paymentDetails['recipient_address'],
                        value: GlobalPretixEthState.paymentDetails['amount']
                    },
                });

                const result = await window.__web3modal.wagmi.core.sendTransaction(transactionConfig);

                await submitSignature(
                    result.hash,
                );
            } catch (e) {
                showError(e);
            }
        }
    }
    try {
        await _submitTransaction();
    } catch (error) {
        showError(error, true);
    }
}

/* Step 4 */
async function submitSignature(transactionHash) {
    async function _submitSignature(transactionHash) {
        const csrf_cookie = getCookie('pretix_csrftoken')
        const url = getTransactionDetailsURL();
        let searchParams = new URLSearchParams({
            signedMessage: GlobalPretixEthState.messageSignature,
            transactionHash: transactionHash,
            selectedAccount: GlobalPretixEthState.signedByAccount,
            csrfmiddlewaretoken: csrf_cookie
        })
        fetch(url, {
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                'X-CSRF-TOKEN': csrf_cookie,
                'HTTP-X-CSRFTOKEN': csrf_cookie,
            },
            method: 'POST',
            body: searchParams
        }
        ).then(
            async (response) => {
                if (response.ok) {
                    showSuccessMessage(transactionHash);
                    await runPeriodicCheck();
                } else {
                    showError("There was an error processing your payment, please contact support. Your payment was sent in transaction " + transactionHash + ".", false)
                }
            }
        )
    }
    try {
        await _submitSignature(transactionHash);
    } catch (error) {
        showError(error, true);
    }
}

export { makePayment }
