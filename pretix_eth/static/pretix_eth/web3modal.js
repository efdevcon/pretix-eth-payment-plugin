"use strict";

var selectedAccount = '';  // address of the currently connected account
var signedByAccount = '';  // address of the account that has signed the message, to check on account chages
var signature = false;  // true if user has sent a message
var signatureRequested = false;
var paymentDetails;
var transactionHashSubmitted = false;


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


async function getPaymentTransactionData(){
    let walletAddress = await getAccount();
    const url = document.getElementById("btn-connect").getAttribute("data-transaction-details-url")
    const response = await fetch(url + '?' + new URLSearchParams({
        sender_address: walletAddress
    }));
    if (response.status >= 400) {
        throw "Failed to fetch order details. If this problem persists, please contact the organizer directly.";
    }
    return await response.json();
}


async function submitSignature(signature, transactionHash, selectedAccount) {
    async function _submitSignature(signature, transactionHash, selectedAccount) {
        let csrf_cookie = getCookie('pretix_csrftoken')
        const url = document.getElementById("btn-connect").getAttribute("data-transaction-details-url")
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
        ).then((response) => {
                if (response.ok) {
                    showSuccessMessage(transactionHash);
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


function init() {
    document.querySelector("#prepare").style.display = "block";

    const providerOptions = {
        walletconnect: {
            package: WalletConnectProvider,
            options: {
                infuraId: "INFURA_ID" // todo required, make it an endpoint
            }
        }
    };
    web3Modal = new Web3Modal({
        cacheProvider: false,
        providerOptions
    });
}


function showError(message = '', reset_state = true) {
    if (transactionHashSubmitted) {
        // do not display errors or reset state after the transaction hash has been successfully submitted to the BE
        message = "";
        reset_state = false;
    } else {
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

    document.getElementById("message-error").innerHTML = message;
    if (reset_state === true) {
        displayOnlyId("prepare");
    }
    try {
        document.getElementById("btn-connect").removeAttribute("disabled");
    } catch (e) {
        return false
    }

    return false
}


function resetErrorMessage() {
    document.getElementById("message-error").innerHTML = '';
}


function displayOnlyId(divId) {
    document.querySelectorAll(".pretix-eth-payment-steps").forEach(
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
    transactionHashSubmitted = true;
    document.getElementById("pretix-eth-transaction-hash").innerText = transactionHash;
    displayOnlyId();
    document.getElementById("success").style.display = "block";
}


async function submitTransaction() {
    async function _submitTransaction() {
        displayOnlyId("send-transaction")
        var selectedAccount = await getAccount();
        let paymentDetails = await getPaymentTransactionData();
        var transactionHash;
        // make the payment
        if (paymentDetails['erc20_contract_address'] !== null) {
            // erc20 transfer
            // TODO !!
            const contract = new window.web3.eth.Contract(
                paymentDetails['erc20_contract_address'],
                ERC20.abi,  // todo
                ethersProvider.getSigner()
            );
            const tx = await contract.transfer(
                to,
                utils.parseUnits(amount, BigNumber.from(asset.decimals))
            );
            transactionHash = tx.hash;
            submitSignature(signature, transactionHash, selectedAccount);
        } else { // crypto transfer
            await window.web3.eth.sendTransaction(
                {
                    from: selectedAccount,
                    to: paymentDetails['recipient_address'],
                    value: paymentDetails['amount'],
                }
            ).on(
                'transactionHash',
                function (transactionHash) {
                    submitSignature(signature, transactionHash, selectedAccount);
                }
            ).on(
                'error', showError
            ).catch(
                showError
            );
        }
    }
    try {
        await _submitTransaction(signature);
    } catch (error) {
        showError(error, true);
    }
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
        displayOnlyId("sign-a-message");
        let selectedAccount = await getAccount();
        let paymentDetails = await getPaymentTransactionData();
        // sign the message
        if (signature && selectedAccount === signedByAccount) {
            // skip the signature step if we have one already
            await submitTransaction();
        } else {
            if (!signatureRequested) {
                signatureRequested = true;
                console.log("Requesting eth_signTypedData_v4:", selectedAccount, message);
                let message = JSON.stringify(paymentDetails['message']);
                window.web3.currentProvider.sendAsync(
                    {
                        method: "eth_signTypedData_v4",
                        params: [selectedAccount, message],
                        from: selectedAccount
                    },
                    async function (err, result) {
                        if (err) {
                            signatureRequested = false;
                            showError(err, true)
                        } else {
                            signature = result.result;
                            signedByAccount = selectedAccount;
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
        _signMessage();
    } catch (error) {
        showError(error);
    }
}


async function initWeb3() {
    let provider;
    try {
        provider = await web3Modal.connect();
    } catch(e) {
        console.log("Could not get a wallet connection", e);
        return;
    }
    window.web3 = new Web3(provider);

    // Subscribe to accounts change
    provider.on("accountsChanged", (accounts) => {
        makePayment();
    });

    // Subscribe to chainId change
    provider.on("chainChanged", (chainId) => {
        makePayment();
    });

    // Subscribe to networkId change
    provider.on("networkChanged", (networkId) => {
        makePayment();
    });

    return provider
}


/**
 * Connect wallet button pressed.
 */
async function web3ModalOnConnect() {
    document.getElementById("btn-connect").setAttribute("disabled", "disabled");
    try {
        await makePayment();
    } catch (error) {
        showError(error)
    }

    document.getElementById("btn-connect").removeAttribute("disabled");
}

window.addEventListener('load', async () => {
    init();
    document.querySelector("#btn-connect").addEventListener("click", web3ModalOnConnect);
});

window.onerror = function (message, file, line, col, error) {
    return showError(error.message)
};

window.addEventListener("error", function (e) {
    return showError(e.error.message)
})

window.addEventListener('unhandledrejection', function (e) {
    return showError()
})
