"use strict";

var selectedAccount = '';  // address of the currently connected account
var signedByAccount = '';  // address of the account that has signed the message, to check on account chages
var hasSigned = false;  // true if user has sent a message
var hasPaid = false;  // true if user has signed the transaction

// todo display errors!
// todo pay with DAI also!

String.prototype.hexEncode = function(){
    var hex, i;
    var result = "";
    for (i=0; i<this.length; i++) {
        hex = this.charCodeAt(i).toString(16);
        result += ("000"+hex).slice(-4);
    }
    return result
}

async function getPaymentTransactionData(walletAddress){
    // todo should say if we're waiting for another payment from that address
    const url = document.getElementById("btn-connect").getAttribute("data-transaction-details-url")
    const response = await fetch(url + '?' + new URLSearchParams({
        sender_address: walletAddress
    }));
    return await response.json();
}

function submitSignature(signedMessage, transactionHash) {
    const url = document.getElementById("btn-connect").getAttribute("data-transaction-details-url")
    debugger;
    // todo post to backend!
}

function init() {
    document.querySelector("#prepare").style.display = "block";
    document.querySelector("#connected").style.display = "none";

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

/*
* Called on "Connect wallet and pay" button click and every chain/account change
*/
async function makePayment() {
  /* todo wrap this in button disable and un-disable and a try-except block  */

  // Get a Web3 instance for the wallet
  const web3 = new Web3(provider);
    const accounts = await web3.eth.getAccounts();
  // MetaMask does not give you all accounts, only the selected account
  selectedAccount = accounts[0];


  const paymentDetails = await getPaymentTransactionData();
  if (paymentDetails['is_signature_submitted'] === true) {
    // todo raise instead?
    showError("It seems that you have paid for this order already.")
    return
  }

  // todo check that payment can be made form this wallet

  // Make sure we're connected to the right chain
  if (paymentDetails['chain_id'] !== await web3.eth.getChainId()) {
    web3.request(
      {
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: paymentDetails['chain_id'].toString(16) }]
      }
    )
  }

  // sign the message

  if (!hasSigned || selectedAccount !== signedByAccount) {
    // todo sig payment secret?
    let signedMessage = await web3.eth.accounts.sign(paymentDetails['message'])
    hasSigned = true
    signedByAccount = selectedAccount
  }

  if (hasSigned) {
    var transactionHash;
    // make payment
    if (asset.contractAddress) { // erc20 transfer
      const contract = new Contract(
        asset.contractAddress,
        ERC20.abi,
        ethersProvider.getSigner()
      );
      const tx = await contract.transfer(
        to,
        utils.parseUnits(amount, BigNumber.from(asset.decimals))
      );
      transactionHash = tx.hash;
      submitSignature(signedMessage, transactionHash);
      } else { // crypto transfer
        try {
          await web3.eth.sendTransaction(
            {
                from: selectedAccount,
                to: paymentDetails['recipient_address'],
                value: paymentDetails['amount'],
            },
            'ASDASDASD' // TODO ?
          ).on(
            'transactionHash',
            function (transactionHash) {
              submitSignature(signedMessage, transactionHash);
            }
          )
        } catch (error) {
            console.error(error); // tslint:disable-line
        }
    }
  }
}

/**
 * Connect wallet button pressed.
 */
async function web3ModalOnConnect() {
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

  document.querySelector("#btn-connect").setAttribute("disabled", "disabled")
  await makePayment(provider);
  document.querySelector("#btn-connect").removeAttribute("disabled")

}

/**
 * Disconnect wallet button pressed.
 */
async function web3ModalOnDisconnect() {

  if(provider.close) {
    await provider.close();

    // If the cached provider is not cleared,
    // WalletConnect will default to the existing session
    // and does not allow to re-scan the QR code with a new wallet.
    // Depending on your use case you may want or want not his behavir.
    await web3Modal.clearCachedProvider();
    provider = null;
  }

  selectedAccount = null;

  // Set the UI back to the initial state
  document.querySelector("#prepare").style.display = "block";
  document.querySelector("#connected").style.display = "none";
}

// debugger;
window.addEventListener('load', async () => {
  init();
  document.querySelector("#btn-connect").addEventListener("click", web3ModalOnConnect);
  document.querySelector("#btn-disconnect").addEventListener("click", web3ModalOnDisconnect);
});
