"use strict";

const BigNumber = window.BigNumber;

const TOKEN_TRANSFER = "0xa9059cbb";
const DAI_TOKEN_ADDRESS = "0x89d24A6b4CcB1B6fAA2625fE562bDD9a23260359";

function convertAmountToRawNumber(value, decimals = 18) {
  return new BigNumber(`${value}`)
    .times(new BigNumber("10").pow(decimals))
    .toString();
}

function convertUtf8ToNumber(utf8) {
  const num = new BigNumber(utf8).toNumber();
  return num;
}

function convertNumberToHex(num, noPrefix) {
  let hex = new BigNumber(num).toString(16);
  hex = sanitizeHex(hex);
  if (noPrefix) {
    hex = removeHexPrefix(hex);
  }
  return hex;
}

async function ethApi(endpoint) {
  const baseUrl = "https://ethereum-api.xyz";
  const res = await fetch(`${baseUrl}${endpoint}`);
  const json = await res.json();
  return json;
}

async function apiGetAccountNonce(address) {
  const chainId = 1;
  const result = await ethApi(
    `/account-nonce?address=${address}&chainId=${chainId}`
  );
  return result;
}

async function apiGetGasPrices() {
  const result = await ethApi(`/gas-prices`);
  return result;
}

function addHexPrefix(hex) {
  if (hex.toLowerCase().s(0, 2) === "0x") {
    return hex;
  }
  return "0x" + hex;
}

function removeHexPrefix(hex) {
  if (hex.toLowerCase().substring(0, 2) === "0x") {
    return hex.substring(2);
  }
  return hex;
}

function sanitizeHex(hex) {
  hex = removeHexPrefix(hex);
  hex = hex.length % 2 !== 0 ? "0" + hex : hex;
  if (hex) {
    hex = addHexPrefix(hex);
  }
  return hex;
}

function padLeft(n, length, z) {
  z = z || "0";
  n = n + "";
  return n.length >= length ? n : new Array(length - n.length + 1).join(z) + n;
}

function getDataString(func, arrVals) {
  let val = "";
  for (let i = 0; i < arrVals.length; i++) {
    val += padLeft(arrVals[i], 64);
  }
  const data = func + val;
  return data;
}

async function formatTransaction(from, to, amount, currency) {
  let value = "";
  let data = "";
  let gasLimit = "";

  if (currency.toUpperCase() === "ETH") {
    value = amount;
    data = "0x";
    gasLimit = 21000;
  } else if (currency.toUpperCase() === "DAI") {
    const tokenAddress = DAI_TOKEN_ADDRESS;
    value = "0x00";
    data = getDataString(TOKEN_TRANSFER, [
      removeHexPrefix(to),
      removeHexPrefix(convertNumberToHex(amount))
    ]);
    gasLimit = 40000;
    to = tokenAddress;
  } else {
    throw new Error(`Asset ${currency} not supported!`);
  }

  const nonce = await apiGetAccountNonce(from);

  const gasPrices = await apiGetGasPrices();
  const gasPrice = convertUtf8ToNumber(
    convertAmountToRawNumber(gasPrices.average.price, 9)
  );

  const tx = {
    from: sanitizeHex(from),
    to: sanitizeHex(to),
    nonce: nonce || "",
    gasPrice: gasPrice || "",
    gasLimit: gasLimit || "",
    value: value || "",
    data: data || "0x"
  };

  return tx;
}
