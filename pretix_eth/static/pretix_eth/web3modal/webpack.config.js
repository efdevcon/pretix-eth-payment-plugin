const path = require('path');
const { WebpackManifestPlugin } = require('webpack-manifest-plugin');

module.exports = {
  mode: 'production',
  entry: './src/web3modal.js',
  output: {
    publicPath: '/static/pretix_eth/web3modal-dist/',
    path: path.resolve(__dirname, '..', 'web3modal-dist'),
    filename: 'web3modal.[contenthash].js',
  },
  plugins: [
    new WebpackManifestPlugin()
  ],
};