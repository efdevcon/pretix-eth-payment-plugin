const qrButton = document.querySelector('#btn-qr');
const qrContainer = document.querySelector('#pretix-eth-qr-div');
qrButton.addEventListener('click', e => toggleQr());

function toggleQr() {
  let isDisplayed = qrContainer.style.display === 'block';
  qrContainer.style.display = isDisplayed ? 'none' : 'block';
}
