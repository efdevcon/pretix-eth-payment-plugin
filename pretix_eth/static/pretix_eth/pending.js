// Toggle QR Code Button

const qrButton = document.querySelector('#btn-qr');
const qrContainer = document.querySelector('#pretix-eth-qr-div');
qrButton.addEventListener('click', e => toggleQr());

function toggleQr() {
  let isDisplayed = qrContainer.style.display === 'block';
  qrContainer.style.display = isDisplayed ? 'none' : 'block';
}

// Copy manual pay address
const address = document.querySelector('#address');
const clipboard = document.querySelector('#clipboard');

clipboard.addEventListener('click', function(e) {
  let range = document.createRange();
  range.selectNode(address);
  window.getSelection().addRange(range);

  try {
    const successful = document.execCommand('copy');
  } catch(err) {
    console.log(err);
  }
  window.getSelection().removeAllRanges();
  // Remove tooltip display
  setTimeout(function() {
    const tooltip = document.querySelector('.tooltip');
    tooltip.style.display = 'none';
  }, 1500);
});
