"use strict";

var selectedAccount = '';  // address of the currently connected account
var signedByAccount = '';  // address of the account that has signed the message, to check on account chages
var signature = false;  // true if user has sent a message
var hasPaid = false;  // true if user has signed the transaction
var paymentDetails;
// todo display errors!
// todo pay with DAI also!
// todo display instructions:
//   1. connect wallet
//   2. check netwwork
//   3. sign a message
//   4. send payment
//   5. do we need a disconnect button?

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
                document.getElementById("pretix-eth-transaction-hash").innerText = transactionHash;
                displayOnlyId("success");
            } else {
                showError("There was an error processing your payment, please contact support. Your payment was sent in transaction "+transactionHash+".")
            }
        }
    )
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

function showError(message) {
    document.querySelector("#message-error").innerHTML = message;
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

async function submitTransaction() {
    // todo move signature to a global var
    async function _submitTransaction() {
        displayOnlyId("send-transaction")
        var selectedAccount = await getAccount();
        var transactionHash;
        // make payment
        if (paymentDetails['erc20_contract_address'] !== null) { // erc20 transfer
            // TODO !!
            const contract = new Contract(
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
            )
        }
    }
    try {
        await _submitTransaction(signature);
    } catch (error) {
        showError(error);
    }
}

async function getAccount() {
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
        const selectedAccount = await getAccount();
        paymentDetails = await getPaymentTransactionData(selectedAccount);
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
            // todo set-correct-network
            // Subscribe to chainId change
            let provider = await web3Modal.connect();
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
    // refresh paymentDetails in case account has changed
    paymentDetails = await getPaymentTransactionData();
    try {
        await _checkChainAndProceed();
    } catch (error) {
        showError(error);
    }
}

/* */
async function signMessage() {
    async function _signMessage() {
        displayOnlyId("sign-a-message");

        let selectedAccount = await getAccount();
        // sign the message
        if (!signature || selectedAccount !== signedByAccount) {
            let message = JSON.stringify(paymentDetails['message']);
            window.web3.currentProvider.sendAsync(
                {
                    method: "eth_signTypedData_v3",
                    params: [selectedAccount, message],
                    from: selectedAccount
                },
                async function (err, result) {
                    if (err) {
                        showError(err)
                        return console.log(err);
                    }
                    signature = result.result;
                    signedByAccount = selectedAccount;
                    await submitTransaction()
                }
            );
        }
    }
    const button = document.querySelector("#retry-sign-a-message")
    button.setAttribute("disabled", "disabled")
    try {
        _signMessage();
    } catch (error) {
        button.removeAttribute("disabled")
        showError(error);
    }
}

/**
 * Connect wallet button pressed.
 */
async function web3ModalOnConnect() {
    let provider;
    try {
        provider = await web3Modal.connect();
    } catch(e) {
        console.log("Could not get a wallet connection", e);
        return;
    }

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

    window.web3 = new Web3(provider);

    document.getElementById("btn-connect").setAttribute("disabled", "disabled");
    await makePayment(provider);
    document.getElementById("btn-connect").removeAttribute("disabled");
    document.getElementById("retry-sign-a-message").onclick = signMessage();
    document.getElementById("retry-send-transaction").onclick = submitTransaction();
}

window.addEventListener('load', async () => {
    init();
    document.querySelector("#btn-connect").addEventListener("click", web3ModalOnConnect);
});
