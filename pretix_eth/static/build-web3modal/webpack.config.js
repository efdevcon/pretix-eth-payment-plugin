const path = require('path');

module.exports = {
  mode: 'production',
  entry: './index.js',
  output: {
    path: path.resolve(__dirname, '..', '3rd_party', 'web3modal'),
    filename: 'web3modal.bundle.js',
  },
};