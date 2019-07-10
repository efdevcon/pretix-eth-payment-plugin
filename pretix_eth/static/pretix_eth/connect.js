"use strict";
document.addEventListener("DOMContentLoaded", function() {
  const Web3Connect = window.Web3Connect.default;
  const Web3 = window.Web3;

  async function onConnect(e) {
    e.preventDefault();
    clearError();

    const web3Connect = new Web3Connect.Core();

    web3Connect.on("connect", async provider => {
      const web3 = new Web3(provider);
      const networkId = await web3.eth.getNetwork();
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
    });

    web3Connect.toggleModal();
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

  document.getElementById(METAMASK_ID).addEventListener("click", onConnect);
  document
    .getElementById(WALLETCONNECT_ID)
    .addEventListener("click", onConnect);
});
