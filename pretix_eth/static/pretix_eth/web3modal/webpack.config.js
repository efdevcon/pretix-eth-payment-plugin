const path = require('path');
const { WebpackManifestPlugin } = require('webpack-manifest-plugin');

module.exports = {
  mode: 'production',
  entry: {
    main: './src/web3modal.js',
    periodicCheck: './src/run_periodic_check.js'
  },
  output: {
    publicPath: '/static/pretix_eth/web3modal-dist/',
    path: path.resolve(__dirname, '..', 'web3modal-dist'),
    filename: 'web3modal.[contenthash].js',
    clean: true
  },
  plugins: [
    new WebpackManifestPlugin()
  ],
};