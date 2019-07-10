"use strict";
document.addEventListener("DOMContentLoaded", function() {
  const Web3Connect = window.Web3Connect.default;
  const Web3 = window.Web3;

  async function onConnect(type) {
    clearError();

    const connector =
      type === "METAMASK"
        ? Web3Connect.ConnectToInjected
        : Web3Connect.ConnectToWalletConnect;

    const provider = await connector();
    const web3 = new Web3(provider);
    const networkId = await web3.eth.net.getId();
    if (networkId !== 1) {
      displayError("Please switch to Ethereum Mainnet");
      return;
    }
    const accounts = await web3.eth.getAccounts();
    const from = accounts[0];
    const tx = await formatTransaction(
      from,
      window.to,
      window.amount,
      window.currency
    );
    const txhash = await web3.eth.sendTransaction(tx);
    return txhash;
  }

  const ERROR_ELM_ID = "connect-error-message";
  const METAMASK_ID = "connect-metamask";
  const WALLETCONNECT_ID = "connect-walletconnect";

  function clearError() {
    const el = document.getElementById(ERROR_ELM_ID);
    el.innerHTML = "";
  }

  function displayError(message) {
    const el = document.getElementById(ERROR_ELM_ID);
    el.innerHTML = message;
    console.error(message);
  }

  document.getElementById(METAMASK_ID).addEventListener("click", e => {
    e.preventDefault();
    onConnect("METAMASK");
  });
  document.getElementById(WALLETCONNECT_ID).addEventListener("click", e => {
    e.preventDefault();
    onConnect("WALLETCONNECT");
  });
});
