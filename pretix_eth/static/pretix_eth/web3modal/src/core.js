"use strict";

import { signTypedData, erc20ABI, getAccount, getNetwork, switchNetwork, sendTransaction, prepareSendTransaction, readContract, prepareWriteContract, writeContract, getProvider } from "@wagmi/core";
import {
    getTransactionDetailsURL,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage,
    getCookie, GlobalPretixEthState, getPaymentTransactionData,
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

                const provider = getProvider();
                const code = await provider.getCode(GlobalPretixEthState.selectedAccount);
                const isSmartContractWallet = code !== '0x';

                if (isSmartContractWallet) {
                    // TODO: ERC1271
                    showError('Smart contract wallets do not work with this version of the plugin.')

                    return;
                }

                GlobalPretixEthState.signatureRequested = true;

                const message = GlobalPretixEthState.paymentDetails['message'];

                const signature = await signTypedData({
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
            const balance = await readContract({
                abi: erc20ABI,
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
                const config = await prepareWriteContract({
                    abi: erc20ABI,
                    address: GlobalPretixEthState.paymentDetails['erc20_contract_address'],
                    functionName: 'transfer',
                    args: [GlobalPretixEthState.paymentDetails['recipient_address'], GlobalPretixEthState.paymentDetails['amount']]
                })

                const result = await writeContract(config)

                await submitSignature(result.hash);
            } catch (e) {
                showError(e);
            }
        } else { // crypto transfer
            displayOnlyId("send-transaction");

            try {
                const transactionConfig = await prepareSendTransaction({
                    request: {
                        to: GlobalPretixEthState.paymentDetails['recipient_address'],
                        value: GlobalPretixEthState.paymentDetails['amount']
                    },
                });

                const result = await sendTransaction(transactionConfig);

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
