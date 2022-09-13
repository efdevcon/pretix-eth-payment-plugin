"use strict";

import {getTransactionDetailsURL, getERC20ABI,
    getPaymentTransactionData,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage, getAccount, getProvider
} from './interface.js';
import {getCookie, GlobalPretixEthState} from './utils.js';
import {runPeriodicCheck} from './periodic_check.js';

// Payment process functions

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

        let provider = await getProvider();

        // Make sure we're connected to the right chain
        const currentChainId = await provider.eth.getChainId()
        if (GlobalPretixEthState.paymentDetails['chain_id'] !== currentChainId) {
            // Subscribe to chainId change

            provider.on("chainChanged", signMessage);

            let desiredChainId = '0x'+GlobalPretixEthState.paymentDetails['chain_id'].toString(16);
            window.ethereum.request(
                {
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: desiredChainId}]
                }
            )
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
                let message = JSON.stringify(GlobalPretixEthState.paymentDetails['message']);
                let provider = await getProvider();
                provider.currentProvider.sendAsync(
                    {
                        method: "eth_signTypedData_v4",
                        params: [GlobalPretixEthState.selectedAccount, message],
                        from: GlobalPretixEthState.selectedAccount
                    },
                    async function (err, result) {
                        if (err) {
                            GlobalPretixEthState.signatureRequested = false;
                            showError(err, true)
                        } else {
                            GlobalPretixEthState.messageSignature = result.result;
                            GlobalPretixEthState.signedByAccount = GlobalPretixEthState.selectedAccount;
                            await submitTransaction();
                        }
                    }
                );
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
        let provider = await getProvider()
        // make the payment
        if (GlobalPretixEthState.paymentDetails['erc20_contract_address'] !== null) {
            let erc20_abi = await getERC20ABI()
            const contract = new provider.eth.Contract(
                erc20_abi,
                GlobalPretixEthState.paymentDetails['erc20_contract_address'],
            );

            let balance = await contract.methods.balanceOf(GlobalPretixEthState.signedByAccount).call();
            if (BigInt(balance) < BigInt(GlobalPretixEthState.paymentDetails['amount'])) {
                showError("Not enough balance to pay using this wallet, please use another currency or payment method, or transfer funds to your wallet and try again.", true);
                return
            }

            displayOnlyId("send-transaction");
            await contract.methods.transfer(
                GlobalPretixEthState.paymentDetails['recipient_address'],
                GlobalPretixEthState.paymentDetails['amount'],
            ).send(
                {from: GlobalPretixEthState.signedByAccount}
            ).on('transactionHash', function(transactionHash){
                submitSignature(
                    transactionHash
                );
            }).on(
                'error', showError
            ).catch(
                showError
            );
        } else { // crypto transfer
            displayOnlyId("send-transaction");
            await provider.eth.sendTransaction(
                {
                    from: GlobalPretixEthState.signedByAccount,
                    to: GlobalPretixEthState.paymentDetails['recipient_address'],
                    value: GlobalPretixEthState.paymentDetails['amount'],
                }
            ).on(
                'transactionHash',
                function (transactionHash) {
                    submitSignature(
                        transactionHash,
                    );
                }
            ).on(
                'error', showError
            ).catch(
                showError
            );
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

export {makePayment}
