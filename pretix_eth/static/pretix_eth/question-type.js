"use strict";

/*
 * payment_eth_html_add_question_type_javascript
 */

// Unpkg imports
const Web3Modal = window.Web3Modal.default;
const WalletConnectProvider = window.WalletConnectProvider.default;
const EvmChains = window.EvmChains;
const Fortmatic = window.Fortmatic;

// Web3modal instance
let web3Modal;

// Chosen wallet provider given by the dialog window
let provider;

// Address of the selected account
let selectedAccount;

function init() {
  // Tell Web3modal what providers we have available.
  // Built-in web browser provider (only one can exist as a time)
  // like MetaMask, Brave or Opera is added automatically by Web3modal
  const providerOptions = {
    walletconnect: {
      package: WalletConnectProvider,
    },

    fortmatic: {
      package: Fortmatic,
    }
  };

  web3Modal = new Web3Modal({
    cacheProvider: false, // optional
    providerOptions, // required
  });
}

async function fetchAccountData() {

  // Get a Web3 instance for the wallet
  const web3 = new Web3(provider);

  // Get connected chain id from Ethereum node
  const chainId = await web3.eth.getChainId();
  // Load chain information over an HTTP API
  const chainData = await EvmChains.getChain(chainId);
  document.querySelector("#network-name").textContent = chainData.name;

  // Get list of accounts of the connected wallet
  const accounts = await web3.eth.getAccounts();

  // MetaMask does not give you all accounts, only the selected account
  selectedAccount = accounts[0];

  document.querySelector("#selected-account").textContent = selectedAccount;

  // Get a handl
  const template = document.querySelector("#template-balance");
  const accountContainer = document.querySelector("#accounts");

  // Purge UI elements any previously loaded accounts
  accountContainer.innerHTML = '';

  // Go through all accounts and get their ETH balance
  const rowResolvers = accounts.map(async (address) => {
    const clone = template.content.cloneNode(true);
    clone.querySelector(".address").textContent = address;
    accountContainer.appendChild(clone);
  });

  // Because rendering account does its own RPC commucation
  // with Ethereum node, we do not want to display any results
  // until data for all accounts is loaded
  await Promise.all(rowResolvers);

  // Display fully loaded UI for wallet data
  document.querySelector("#prepare").style.display = "none";
  document.querySelector("#connected").style.display = "block";
}

async function refreshAccountData() {
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

async function onConnect() {

  // Setting this null forces to show the dialogue every time
  // regardless if we play around with a cacheProvider settings
  // in our localhost.
  web3Modal.providerController.cachedProvider = null;
  try {
    provider = await web3Modal.connect();
  } catch(e) {
    console.log("Could not get a wallet connection", e);
    return;
  }
  
  const web3 = new Web3(provider);
  const accounts = await web3.eth.getAccounts();
  document.querySelector('#id_3-question_1').value = accounts[0];

  await refreshAccountData();
}

async function onDisconnect() {

  if(provider.close) {
    await provider.close();
    provider = null;
  }

  selectedAccount = null;

  // Set the UI back to the initial state
  document.querySelector("#prepare").style.display = "block";
  document.querySelector("#connected").style.display = "none";
}

window.addEventListener('load', async () => {
  init();
  document.querySelector("#btn-connect").addEventListener("click", onConnect);
  document.querySelector("#btn-disconnect").addEventListener("click", onDisconnect);
});

// from our marked fields obtain all ids of desired questions
function get_payment_eth_question_ids(class_name) {
    var info_elements = document.getElementsByClassName(class_name);
    var payment_eth_question_ids = [];
    for (var i = 0; i < info_elements.length; i++) {
        payment_eth_question_ids = payment_eth_question_ids.concat(
            info_elements[i].value.split(',')
        )
    }
    return payment_eth_question_ids;
}

// try to get question element and do desired changes on it
function change_element(element_id) {
    var element = document.getElementById(element_id);
    if (!element) {
        return;
    }
    // do the actual change of an element
    element.style.background = "pink";
}

$(function () {
    // there are `payment_eth_info` hidden inputs with list of IDs
    // of the other fields we want to change functionality
    var payment_eth_question_ids = get_payment_eth_question_ids('payment_eth_info');
    for (var i = 0; i < payment_eth_question_ids.length; i++) {
        change_element(payment_eth_question_ids[i]);
    }
  const formGroupElements = document.querySelectorAll("div.form-group");

  const lastFormGroupElement = formGroupElements.item(formGroupElements.length - 1);
  const inputElement = document.querySelector("input[name='3-question_1']");
  const addressButton = document.createElement("button");
  addressButton.textContent = "Add Wallet Address";
  addressButton.id = "btn-connect";
  addressButton.style.cssText = "margin: 8px 0 0 12px; border-radius: 5px; padding: 8px; box-shadow: 0 3px 6px 0 rgba(0, 0, 0, 0.16); background: linear-gradient(102deg, #2ea4d8 4%, #0461b5 87%); color: white; font-weight: 500; font-size: 16px;";
  lastFormGroupElement.append(addressButton);
});
