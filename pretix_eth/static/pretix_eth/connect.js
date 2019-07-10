"use strict";
document.addEventListener("DOMContentLoaded", function() {
  const WalletConnect = window.WalletConnect.default;
  const qrcode = window.WalletConnectQRCodeModal.default;
  const Web3 = window.Web3;

  async function onMetaMask() {
    clearError();
    const provider = await initMetaMask();
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
  }

  async function onWalletConnect() {
    clearError();
    const wc = await initWalletConnect();
    const chainId = wc.chainId;
    if (chainId !== 1) {
      displayError("Please switch to Ethereum Mainnet");
      return;
    }
    const accounts = wc.accounts;
    const from = accounts[0];
    const tx = await formatTransaction(
      from,
      window.to,
      window.amount,
      window.currency
    );
    const txhash = await wc.sendTransaction(tx);
    return txhash;
  }

  async function initMetaMask() {
    let provider = null;
    if (window.ethereum) {
      provider = window.ethereum;
      try {
        await window.ethereum.enable();
      } catch (error) {
        throw new Error("User Rejected");
      }
    } else if (window.web3) {
      provider = window.web3.currentProvider;
    } else {
      throw new Error("No Web3 Provider found");
    }
    return provider;
  }

  function initWalletConnect() {
    return new Promise(async (resolve, reject) => {
      const wc = new WalletConnect({
        bridge: "https://bridge.walletconnect.org"
      });

      if (!wc.connected) {
        await wc.createSession();
        qrcode.open(wc.uri, () => {
          console.log("QR Code Modal closed");
        });
      } else {
        resolve(wc);
      }

      wc.on("connect", (error, payload) => {
        if (error) {
          reject(error);
        }

        qrcode.close();

        resolve(wc);
      });
    });
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

  document.getElementById(METAMASK_ID).addEventListener("click", onMetaMask);
  document
    .getElementById(WALLETCONNECT_ID)
    .addEventListener("click", onWalletConnect);
});
