"use strict";

import {getTransactionDetailsURL, getERC20ABI,
    getPaymentTransactionData, runPeriodicCheck,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage, getAccount, initWeb3
} from './interface.js';

import {getCookie, GlobalPretixEthState} from './utils.js';

// Payment process functions

async function submitSignature(signature, transactionHash, selectedAccount) {
    async function _submitSignature(signature, transactionHash, selectedAccount) {
        let csrf_cookie = getCookie('pretix_csrftoken')
        const url = getTransactionDetailsURL();
        let searchParams = new URLSearchParams({
            signedMessage: signature,
            transactionHash: transactionHash,
            selectedAccount: selectedAccount,
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
        await _submitSignature(signature, transactionHash, selectedAccount);
    } catch (error) {
        showError(error, true);
    }
}


async function submitTransaction() {
    async function _submitTransaction() {
        if (GlobalPretixEthState.transactionRequested === true) {
            return
        }
        GlobalPretixEthState.transactionRequested = true

        const selectedAccount = await getAccount();
        let paymentDetails = await getPaymentTransactionData();
        // make the payment
        if (paymentDetails['erc20_contract_address'] !== null) {
            let erc20_abi = await getERC20ABI()
            const contract = new window.web3.eth.Contract(
                erc20_abi,
                paymentDetails['erc20_contract_address'],
            );

            let balance = await contract.methods.balanceOf(selectedAccount).call();
            if (BigInt(balance) < BigInt(paymentDetails['amount'])) {
                showError("Not enough balance to pay using this wallet, please use another currency or payment method, or transfer funds to your wallet and try again.", true);
                return
            }

            displayOnlyId("send-transaction");
            await contract.methods.transfer(
                paymentDetails['recipient_address'],
                paymentDetails['amount'],
            ).send({from: selectedAccount}).on('transactionHash', function(transactionHash){
                submitSignature(
                    GlobalPretixEthState.signature,
                    GlobalPretixEthState.transactionHash,
                    GlobalPretixEthState.selectedAccount);
            }).on(
                'error', showError
            ).catch(
                showError
            );
        } else { // crypto transfer
            displayOnlyId("send-transaction");
            await window.web3.eth.sendTransaction(
                {
                    from: selectedAccount,
                    to: paymentDetails['recipient_address'],
                    value: paymentDetails['amount'],
                }
            ).on(
                'transactionHash',
                function (transactionHash) {
                    submitSignature(
                        GlobalPretixEthState.signature,
                        transactionHash,
                        GlobalPretixEthState.selectedAccount
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
        await _submitTransaction(GlobalPretixEthState.signature);
    } catch (error) {
        showError(error, true);
    }
}

/*
* Called on "Connect wallet and pay" button click and every chain/account change
*/
async function makePayment() {
    async function _checkChainAndProceed() {
        // refresh paymentDetails in case account has changed
        let paymentDetails = await getPaymentTransactionData();
        if (paymentDetails['is_signature_submitted'] === true) {
            showError("It seems that you have paid for this order already.")
            return
        }
        if (paymentDetails['has_other_unpaid_orders'] === true) {
            showError("Please wait for other payments from your wallet to be confirmed before submitting another transaction.")
            return
        }

        // Make sure we're connected to the right chain
        const currentChainId = await window.web3.eth.getChainId()
        if (paymentDetails['chain_id'] !== currentChainId) {
            // Subscribe to chainId change
            let provider = await initWeb3();
            provider.on("chainChanged", (chainId) => {
                signMessage();
            });

            // Subscribe to networkId change
            provider.on("networkChanged", (networkId) => {
                signMessage();
            });

            let desiredChainId = '0x'+paymentDetails['chain_id'].toString(16);
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

/* */
async function signMessage() {
    async function _signMessage() {
        let selectedAccount = await getAccount();
        let paymentDetails = await getPaymentTransactionData();
        // sign the message
        if (GlobalPretixEthState.signature && selectedAccount === GlobalPretixEthState.signedByAccount) {
            // skip the signature step if we have one already
            await submitTransaction();
        } else {
            if (!GlobalPretixEthState.signatureRequested) {
                displayOnlyId("sign-a-message");
                GlobalPretixEthState.signatureRequested = true;
                let message = JSON.stringify(paymentDetails['message']);
                console.log("Requesting eth_signTypedData_v4:", selectedAccount, message);
                window.web3.currentProvider.sendAsync(
                    {
                        method: "eth_signTypedData_v4",
                        params: [selectedAccount, message],
                        from: selectedAccount
                    },
                    async function (err, result) {
                        if (err) {
                            GlobalPretixEthState.signatureRequested = false;
                            showError(err, true)
                        } else {
                            GlobalPretixEthState.signature = result.result;
                            GlobalPretixEthState.signedByAccount = selectedAccount;
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
    }
}


export {makePayment}
