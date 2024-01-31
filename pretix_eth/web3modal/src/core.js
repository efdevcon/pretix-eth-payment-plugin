"use strict";

import { signTypedData, erc20ABI, getAccount, getNetwork, switchNetwork, sendTransaction, readContract, writeContract, getPublicClient } from "@wagmi/core";
import {
    getTransactionDetailsURL,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage,
    getCookie, GlobalPretixEthState, getPaymentTransactionData,
} from './interface.js';
import { runPeriodicCheck } from './periodic_check.js';

function validate_txhash(addr) {
    return /^0x([A-Fa-f0-9]{64})$/.test(addr);
}

const checkResult = (result) => {
    try {
        const parsed = JSON.parse(result);

        if (parsed.error) {
            throw parsed.error;
        }
    } catch (e) {

    }
}

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

        const network = await getNetwork();
        const networkIsWrong = network.chain.id !== GlobalPretixEthState.paymentDetails.chain_id

        if (networkIsWrong) {
            try {
                displayOnlyId("switching-chains");

                await switchNetwork({
                    chainId: GlobalPretixEthState.paymentDetails.chain_id,
                })
            } catch (e) {
                console.error(e);

                showError("There was an error switching chains. You may have to manually switch to the appropriate chain in your connected wallet, and then try again.")
            }
        } else {
            await sign();
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
async function sign() {
    async function _sign() {
        GlobalPretixEthState.selectedAccount = await getAccount()?.address;
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
                const client = getPublicClient();
                const code = await client.getBytecode({ address: GlobalPretixEthState.selectedAccount });
                const isSmartContractWallet = !!code;

                if (isSmartContractWallet) {
                    const checkIsSafeWallet = async () => {
                        const safeUrl = `https://safe-transaction-${GlobalPretixEthState.safeNetworkIdentifier}.safe.global/api/v1/safes/${GlobalPretixEthState.selectedAccount}`;
                        const response = await fetch(safeUrl);

                        return response.ok;
                    }

                    const isSafeWallet = await checkIsSafeWallet();

                    // We only support safe in this version of the plugin
                    if (!isSafeWallet) {
                        showError('This version of the crypto payment plugin only supports Safe wallet (on supported networks) and EOA wallets. Please connect another wallet.');

                        GlobalPretixEthState.signatureRequested = false;

                        return;
                    }

                    const signature = await signTypedData(message);

                    // For some ungodly reason wagmi doesn't error out on some errors - have to check the return value for errors to avoid any issues
                    checkResult(signature);

                    // Validate signature on the backend before proceeding:
                    const url = new URL(window.location.origin + window.__validateSignatureUrl);
                    url.searchParams.append('signature', signature);
                    url.searchParams.append('sender', GlobalPretixEthState.selectedAccount);
                    const csrf_cookie = getCookie('pretix_csrftoken')
                    const response = await fetch(url.href, {
                        headers: {
                            "Content-Type": "application/x-www-form-urlencoded",
                            'X-CSRF-TOKEN': csrf_cookie,
                            'HTTP-X-CSRFTOKEN': csrf_cookie,
                        },
                        method: 'GET'
                    });

                    GlobalPretixEthState.messageSignature = signature;
                    GlobalPretixEthState.signedByAccount = GlobalPretixEthState.selectedAccount;

                    // When signature is valid response will be 200 and we can proceed, otherwise show error
                    if (response.ok) {
                        await submitTransaction();
                    } else {
                        showError('EIP1271 validation error: unable to verify signature; your wallet may not be supported.')

                        GlobalPretixEthState.signatureRequested = false;

                        return;
                    }
                } else {
                    const signature = await signTypedData(message)

                    // For some ungodly reason wagmi doesn't error out on some errors - have to check the return value for errors to avoid any issues
                    checkResult(signature);

                    GlobalPretixEthState.messageSignature = signature;
                    GlobalPretixEthState.signedByAccount = GlobalPretixEthState.selectedAccount;

                    await submitTransaction();
                }
            } else {
                console.log("Requesting more than one message signature.");
            }
        }
    }

    try {
        await _sign();
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
            const daiContractAddress = GlobalPretixEthState.paymentDetails['erc20_contract_address'];

            const balance = await readContract({
                abi: erc20ABI,
                address: daiContractAddress,
                functionName: 'balanceOf',
                args: [GlobalPretixEthState.selectedAccount],
            });

            if (BigInt(balance) < BigInt(GlobalPretixEthState.paymentDetails['amount'])) {
                showError("Not enough balance to pay using this wallet, please use another currency or payment method, or transfer funds to your wallet and try again.", true);
                return
            }

            displayOnlyId("send-transaction");

            try {
                const result = await writeContract({
                    abi: erc20ABI,
                    address: daiContractAddress,
                    functionName: 'transfer',
                    args: [GlobalPretixEthState.paymentDetails['recipient_address'], GlobalPretixEthState.paymentDetails['amount']]
                })

                const valid = validate_txhash(result.hash);

                if (!valid) throw 'Invalid transaction hash';

                checkResult(result);

                await submitSignature(result.hash);
            } catch (e) {
                showError(e);
            }
        } else { // crypto transfer
            displayOnlyId("send-transaction");

            try {
                const result = await sendTransaction({
                    to: GlobalPretixEthState.paymentDetails['recipient_address'],
                    value: GlobalPretixEthState.paymentDetails['amount']
                });

                const valid = validate_txhash(result.hash);

                if (!valid) throw 'Invalid transaction hash';

                await submitSignature(result.hash);
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
    // If we're on Safe app, our transaction hash is the safe transaction hash - we'll need to check if it's a safe transaction and if so, save the url for later
    const checkIfSafeAppTransaction = async (transactionHash) => {
        // Wrapping in try/catch for the edge case that its a safe transaction but their endpoint is down and fetch errors out - at least we'll still have some information to work with 
        // during manual resolution rather than the TX hash being entirely lost on our end
        try {
            const safeUrl = `https://safe-transaction-${GlobalPretixEthState.safeNetworkIdentifier}.safe.global/api/v1/multisig-transactions/${transactionHash}`
            const response = await fetch(safeUrl);

            // If 2xx reply we'll know we have a safe transaction - we'll return the url so we can use it later when confirming payment
            // We could also return the safe tx and construct the url on the python side, 
            // but I think it's better to do it here so we only have to do it once / only need to maintain the api list in one place
            if (response.ok) {
                return safeUrl;
            }
        } catch (e) {
            return;
        }
    }

    async function _submitSignature(transactionHash) {
        const safeAppTransactionUrl = await checkIfSafeAppTransaction(transactionHash);
        const csrf_cookie = getCookie('pretix_csrftoken')
        const url = getTransactionDetailsURL();
        let searchParams = new URLSearchParams({
            signedMessage: GlobalPretixEthState.messageSignature,
            transactionHash: transactionHash,
            selectedAccount: GlobalPretixEthState.signedByAccount,
            csrfmiddlewaretoken: csrf_cookie
        })

        if (safeAppTransactionUrl) {
            searchParams.append('safeAppTransactionUrl', safeAppTransactionUrl);
        }

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
                    showSuccessMessage(transactionHash, safeAppTransactionUrl);
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
