"use strict";

const WalletConnect = window.WalletConnect.default;
const qrcode = window.WalletConnectQRCodeModal.default;
const Web3 = window.Web3;

async function onMetaMask() {
  const provider = await initMetaMask();
  const web3 = new Web3(provider);
  const accounts = await web3.eth.getAccounts();
  const from = accounts[0];
  const tx = formatTransaction(from, to, amount, asset);
  const txhash = await web3.eth.sendTransaction(tx);
  return txhash;
}

async function onWalletConnect() {
  const wc = await initWalletConnect();
  const accounts = wc.accounts;
  const from = accounts[0];
  const tx = formatTransaction(from, to, amount, asset);
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
  return new Promise((resolve, reject) => {
    const wc = new WalletConnect({
      bridge: "https://bridge.walletconnect.org"
    });

    if (!wc.connected) {
      wc.createSession().then(() => {
        const uri = wc.uri;

        qrcode.open(uri, () => {
          console.log("QR Code Modal closed");
        });
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
