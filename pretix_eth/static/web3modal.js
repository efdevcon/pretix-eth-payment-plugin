"use strict";

// todo use static json list
const evmChains = window.EvmChains;

// todo list of params - endpoint?
/*
*
* infura id
* gasPrice: "20000000000",
* gas: "21000",
* to: '0x3535353535353535353535353535353535353535',
* value: "1000000000000000000",
* data: ""
*
* endpoints:
* transaction info
* submit signed transaction
*
* */

function init() {
    document.querySelector("#prepare").style.display = "block";
    document.querySelector("#connected").style.display = "none";

    const providerOptions = {
        walletconnect: {
            package: WalletConnectProvider, // required
            options: {
                infuraId: "INFURA_ID" // todo required
            }
        }
    };

    web3Modal = new Web3Modal({
        cacheProvider: false,
        providerOptions
    });
}

String.prototype.hexEncode = function(){
    var hex, i;

    var result = "";
    for (i=0; i<this.length; i++) {
        hex = this.charCodeAt(i).toString(16);
        result += ("000"+hex).slice(-4);
    }

    return result
}

async function fetchAccountData() {

  // Get a Web3 instance for the wallet
  const web3 = new Web3(provider);

  // Get connected chain id from Ethereum node
  const chainId = await web3.eth.getChainId();
  // Load chain information over an HTTP API
  const chainData = evmChains.getChain(chainId);
  document.querySelector("#network-name").textContent = chainData.name;
  // Get list of accounts of the connected wallet
  const accounts = await web3.eth.getAccounts();
  // MetaMask does not give you all accounts, only the selected account
  selectedAccount = accounts[0];

  // todo get values from an endpoint
  try {
    const signedTransaction = web3.eth.signTransaction({
      from: selectedAccount,
      gasPrice: "20000000000",
      gas: "21000",
      to: '0x3535353535353535353535353535353535353535',
      value: "1000000000000000000",
      data: ""
    }, '').then(console.log);
    console.log("signedMessage", signedMessage)
  } catch (error) {
    console.error(error); // tslint:disable-line
  }
  // todo submit values to an endpoint
  // Display fully loaded UI for wallet data
  document.querySelector("#prepare").style.display = "none";
  document.querySelector("#connected").style.display = "block";
}



/**
 * Fetch account data for UI when
 * - User switches accounts in wallet
 * - User switches networks in wallet
 * - User connects wallet initially
 */
async function refreshAccountData2() {

  // If any current data is displayed when
  // the user is switching acounts in the wallet
  // immediate hide this data
  document.querySelector("#connected").style.display = "none";
  document.querySelector("#prepare").style.display = "block";

  // Disable button while UI is loading.
  // fetchAccountData() will take a while as it communicates
  // with Ethereum node via JSON-RPC and loads chain data
  // over an API call.
  document.querySelector("#btn-connect").setAttribute("disabled", "disabled")
  await fetchAccountData(provider);
  document.querySelector("#btn-connect").removeAttribute("disabled")
}
// -------------------------

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
    fetchAccountData();
  });

  // Subscribe to chainId change
  provider.on("chainChanged", (chainId) => {
    fetchAccountData();
  });

  // Subscribe to networkId change
  provider.on("networkChanged", (networkId) => {
    fetchAccountData();
  });

  await refreshAccountData2();
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
