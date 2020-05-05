"use strict";

/*
 * payment_eth_html_add_question_type_javascript
 */

// Imports
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
      options: {
        infuraId: "123456789b123456789" // Not a real id
      }
    },
  };

  web3Modal = new Web3Modal({
    cacheProvider: false, // optional
    providerOptions, // required
  });
}

async function refreshAccountData(e) {
  const web3 = new Web3(provider);
  const accounts = await web3.eth.getAccounts();
  const buttonId = e.target.id;
  const inputElement = document.querySelector(`input#${buttonId}`);
  inputElement.value = accounts[0];
  await disconnect();
}

async function onConnect(e) {
  web3Modal.providerController.cachedProvider = null;
  try {
    provider = await web3Modal.connect();
  } catch(e) {
    console.log("Could not get a wallet connection", e);
    return;
  }
  await refreshAccountData(e);
}

async function disconnect() {
  if (provider.close) {
    await provider.close();
    provider = null;
  }
  selectedAccount = null;
}

window.addEventListener('load', async () => {
  init();
  const addressButtons = document.querySelectorAll(".btn-connect");
  for (let i of addressButtons) {
    i.addEventListener('click', e => onConnect(e));
  }
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


$(function () {
  // Get unique Ids
  const [...targetElements] = get_payment_eth_question_ids('payment_eth_info');

  // Add Button Elements
  for (let i of targetElements) {
    let el = document.querySelector(`#${i}`);
    let addressButton = document.createElement("button");
    addressButton.setAttribute('type', 'button');
    addressButton.textContent = "Add Wallet Address";
    addressButton.id = i;
    addressButton.classList.add("btn", "btn-connect", "btn-block", "btn-primary", "btn-lg");
    addressButton.style.cssText = "max-width: 360px; margin-top: 8px;";
    el.parentNode.append(addressButton);
  }
});
