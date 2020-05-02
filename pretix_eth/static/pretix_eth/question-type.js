"use strict";

/*
 * payment_eth_html_add_question_type_javascript
 */

// Unpkg imports
const Web3Modal = window.Web3Modal.default;
const WalletConnectProvider = window.WalletConnectProvider.default;
const EvmChains = window.EvmChains;

// Web3modal instance
let web3Modal;

// Chosen wallet provider given by the dialog window
let provider;

// Address of the selected account
let selectedAccount;

function init() {
  const providerOptions = {
    walletconnect: {
      package: WalletConnectProvider,
    },
  };

  web3Modal = new Web3Modal({
    cacheProvider: false, // optional
    providerOptions, // required
  });
}

async function refreshAccountData() {
  const web3 = new Web3(provider);
  const accounts = await web3.eth.getAccounts();
  const inputElements = document.querySelectorAll('input'); 
  /* IMPORTANT: length -2 because of a hidden input field at the end.
   * If the input field for this page changes this value will likely need
   * to be adjusted. */
  const targetedInputElement = inputElements.item(inputElements.length - 2);
  targetedInputElement.value = accounts[0];
}

async function onConnect() {
  web3Modal.providerController.cachedProvider = null;
  try {
    provider = await web3Modal.connect();
  } catch(e) {
    console.log("Could not get a wallet connection", e);
    return;
  }
  await refreshAccountData();
}
window.addEventListener('load', async () => {
  init();
  document.querySelector("#btn-connect").addEventListener("click", onConnect);
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

  // Grandparent Element
  const formGroupElements = document.querySelectorAll("div.form-group");
  const lastFormGroupElement = formGroupElements.item(formGroupElements.length - 1);

  // Parent Element
  const columnElement = lastFormGroupElement.childNodes.item(1);
  
  // Warning Text Element
  const warningText = document.createElement("p");
  warningText.style.cssText = "font-weight: 600; line-height: 1.5; margin-top: 4px;"
  warningText.classList.add("warningText");
  const warningTextContent = document.createTextNode("Please use a non-custodial address. E.g. not Coinbase, Gemini, etc.");
  warningText.appendChild(warningTextContent);

  // Button Element
  const addressButton = document.createElement("button");
  addressButton.textContent = "Add Wallet Address";
  addressButton.id = "btn-connect";
  addressButton.classList.add("btn", "btn-block", "btn-primary", "btn-lg");
  addressButton.style.cssText = "max-width: 360px; margin-top: 8px;";
  columnElement.append(addressButton);
  columnElement.appendChild(warningText);
});
