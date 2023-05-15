"use strict";

import { signMessage, signTypedData, erc20ABI, getAccount, getNetwork, switchNetwork, sendTransaction, readContract, prepareWriteContract, writeContract, getPublicClient } from "@wagmi/core";
import {
    getTransactionDetailsURL,
    showError, resetErrorMessage, displayOnlyId,
    showSuccessMessage,
    getCookie, GlobalPretixEthState, getPaymentTransactionData,
} from './interface.js';
import { runPeriodicCheck } from './periodic_check.js';
// import { hashMessage } from 'viem'

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

                // Safe stuff, doesn't work for now...
                // await client.request({
                //     method: 'safe_setSettings',
                //     params: [{ offChainSigning: true }],
                // })

                // If connected wallet is an SC wallet, conform to EIP1271
                if (isSmartContractWallet) {
                    // Constructing the message to sign. 
                    // TODO: could sign using EIP721 but wasn't sure how to generate a corresponding hash for this
                    const formattedMessage = GlobalPretixEthState.selectedAccount + message.message['receiver_address'] + message.message['order_code'] + message.message['chain_id'];
                    const signature = await signMessage({ message: formattedMessage });
                    // const msgHash = hashMessage(formattedMessage);

                    // const eip1271Abi = [
                    //     {
                    //         inputs: [{ name: "_hash", type: "bytes32" }, { name: "_signature", type: "bytes" }],
                    //         name: "isValidSignature",
                    //         outputs: [{ name: "magicValue", type: "bytes4" }],
                    //         stateMutability: "view",
                    //         type: "function",
                    //     }
                    // ];

                    // const magicValue = '0x1626ba7e';
                    // const response = await readContract({
                    //     abi: eip1271Abi,
                    //     address: GlobalPretixEthState.selectedAccount,
                    //     functionName: 'isValidSignature',
                    //     args: [msgHash, signature],
                    // });

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

                    if (response.ok) {
                        await submitTransaction();
                    } else {
                        showError('EIP1271 error: unable to verify signature; your wallet may not be supported.')

                        return;
                    }
                } else {
                    const signature = await signTypedData(message)

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

                const { hash } = await writeContract(config)

                await submitSignature({ hash });
            } catch (e) {
                showError(e);
            }
        } else { // crypto transfer
            displayOnlyId("send-transaction");

            try {
                const { hash } = await sendTransaction({
                    to: GlobalPretixEthState.paymentDetails['recipient_address'],
                    value: GlobalPretixEthState.paymentDetails['amount'],
                    data: '' // Argent needs this to be defined for some reason
                });

                await submitSignature({
                    hash
                });
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
