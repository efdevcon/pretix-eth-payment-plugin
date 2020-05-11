'use strict';

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
        infuraId: '123456789b123456789' // Not a real id
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
    console.log('Could not get a wallet connection', e);
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
  const addressButtons = document.querySelectorAll('.btn-connect');
  for (let i of addressButtons) {
    i.addEventListener('click', e => onConnect(e));
  }
  const submitButton = document.querySelector('.btn-primary');
  submitButton.addEventListener('click', checkValidity);
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

function checkValidity() {
  // Remove Input Warning DOM Nodes to avoid duplicate warnings
  const warningElements = document.querySelectorAll('.alert-danger');
  for (let i of warningElements) {
    i.parentNode.removeChild(i);
  }
  // Create an array of Address Input values and evaluate
  // Prevent form submission if validityState is false
  const [...addressIds] = get_payment_eth_question_ids('payment_eth_info');
  let addressInputValues = [];
  for (let i of addressIds) {
    let addressInputElements = document.querySelector(`input#${i}`);
    addressInputValues.push(addressInputElements.value);
  }
  const validityState = isValidAddressInput(addressInputValues);
  const submitButton = document.querySelector('.btn-primary');
  if (validityState === false) {
    submitButton.setAttribute('type', 'button');
  } else {
    submitButton.setAttribute('type', 'submit');
  }
}

function createWarning(inputNo) {
  const [...addressIds] = get_payment_eth_question_ids('payment_eth_info');
  let firstIssue = true;
  for (let i = 0; i < addressIds.length; i++) {
    if (i === inputNo) {
      let inputElement = document.querySelector(`input#${addressIds[i]}`);
      let invalidInputWarning = document.createElement('div');
      invalidInputWarning.classList.add('alert', 'alert-danger');
      invalidInputWarning.setAttribute('role', 'alert');
      invalidInputWarning.style.cssText = 'margin-top: 8px;';
      invalidInputWarning.textContent = 'Invalid input. Please enter either a valid wallet address, or a valid ENS address.';
      inputElement.parentNode.insertBefore(invalidInputWarning, inputElement.parentNode.lastChild);
      if (firstIssue) {
        inputElement.scrollIntoView({alignToTop: true, behavior: 'smooth'});
        firstIssue = false;
      }
    }
  }
}

function createDuplicateWarning() {
  const [...addressIds] = get_payment_eth_question_ids('payment_eth_info');
  let firstIssue = true;
  let values = [];
  for (let i of addressIds) {
    const inputElement = document.querySelector(`#${i}`);
    if (values.includes(inputElement.value)) {
      let duplicateInputWarning = document.createElement('div');
      duplicateInputWarning.classList.add('alert', 'alert-danger');
      duplicateInputWarning.setAttribute('role', 'alert');
      duplicateInputWarning.style.cssText = 'margin-top: 8px;';
      duplicateInputWarning.textContent = 'Invalid input. We cannot send two NFTs to the same address. Please add a separate wallet address for each ticket.';
      inputElement.parentNode.insertBefore(duplicateInputWarning, inputElement.parentNode.lastChild);
      if (firstIssue) {
        inputElement.scrollIntoView({alignToTop: true, behavior: 'smooth'});
        firstIssue = false;
      }
    } else {
      values.push(inputElement.value);
    }
  }
}

function isValidAddressInput(inputs) {
  let responses = [];
  for (let input of inputs) {
    if ((input !== '') && responses.includes(input)) {
      createDuplicateWarning();
      return false;
    } else {
      responses.push(input);
    }
  }
  /* We evaluate a bool array instead of instantly returning for 2 reasons:
   * 1. To avoid false positives
   * 2. So we know which input value is invalid */
  let validityChecks = [];
  for (let response of responses) {
    if (isBlank(response)) {
      validityChecks.push(true);
      break;
    }
    if (isEnsAddress(response)) {
      validityChecks.push(true);
    } else {
      let web3 = new Web3(provider);
      validityChecks.push(web3.utils.isAddress(response));
    }
  }
  if (validityChecks.includes(false)) { 
    for (let i = 0; i < validityChecks.length; i++) {
      if (validityChecks[i] === false) {
        createWarning(i);
      }
    }
    return false;
  } else {
    return true;
  }
}

function isBlank(str) {
  return (str === '') ? true : false;
}

function isEnsAddress(address) {
  const fourCharTld = ['.eth', '.xyz', '.art'];
  const fiveCharTld = ['.luxe', '.kred', '.club'];
  for (let i of fourCharTld) {
    if (i === address.slice(address.length - 4)) {
      return true;
    }
  }
  for (let i of fiveCharTld) {
    if (i === address.slice(address.length - 5)) {
      return true;
    }
  }
  return false;
}

$(function () {
  // Detect useragent, and disable button if Firefox
  const isBrowserFirefox = navigator.userAgent.search('Firefox');

  // Get unique Ids
  const [...targetElements] = get_payment_eth_question_ids('payment_eth_info');

  // Add Button Elements or Firefox Warning Text
  for (let i of targetElements) {
    // Button Element
    let el = document.querySelector(`#${i}`);
    let addressButton = document.createElement('button');
    addressButton.setAttribute('type', 'button');
    addressButton.textContent = 'Add Wallet Address';
    addressButton.id = i;
    addressButton.classList.add('btn', 'btn-connect', 'btn-block', 'btn-lg');
    addressButton.style.cssText = 'max-width: 360px; margin-top: 8px; background: #8e44b3; border-color: #8e44b3; color: white;';

    // Firefox Warning Text Element
    let warningText = document.createElement('p');
    warningText.appendChild(document.createTextNode('Unfortunately the web3 API we use to automatically add a wallet address is not supported in Firefox at this time. Please carefully copy and paste your wallet address into the above field.'));
    warningText.style.cssText = 'margin-top: 8px;';

    // Insert Node
    if (isBrowserFirefox === -1) {
      el.parentNode.append(addressButton);
    } else {
      el.parentNode.append(warningText);
    }
  }
});
