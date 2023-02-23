"use strict";

import { showError, GlobalPretixEthState, loadChainsJSON, signIn } from './interface.js';
import { makePayment } from './core.js';

// const chainToWagmiFormat = (chain) => {
//     return {
//         id: chain.chainId,
//         name: chain.name,
//         network: (() => {
//             switch (chain.chainId) {
//                 case 42161:
//                     return 'arbitrum';
//                 case 10:
//                     return 'optimism';
//                 case 1:
//                     return 'homestead';
//             }
//         })(),
//         nativeCurrency: chain.nativeCurrency,
//         rpcUrls: {
//             default: {
//                 http: chain.rpc.length > 2 ? chain.rpc.slice(2) : chain.rpc[0]
//             },
//             // public: {
//             //     http: chain.rpc[0]
//             // },
//         },
//         blockExplorers: chain.explorers ? {
//             default: {
//                 name: chain.explorers[0].name,
//                 url: chain.explorers[0].url
//             }
//             // public: {
//             //     http: chain.rpc[0]
//             // },
//         } : undefined,
//     }
// }

async function init() {
    GlobalPretixEthState.elements.divPrepare.style.display = "block";

    // await loadChainsJSON();

    const {
        wagmi: {
            core: {
                configureChains,
                watchNetwork,
                createClient,
                watchAccount
            },
            chains: {
                arbitrum,
                arbitrumGoerli,
                mainnet,
                sepolia,
                goerli,
                optimism,
                optimismGoerli,
                zkSync
            }
        },
        web3modal: {
            ethereum: {
                EthereumClient,
                modalConnectors,
                walletConnectProvider,
            },
            html: {
                Web3Modal
            }
        },
    } = window.__web3modal

    // const sepolia = chainToWagmiFormat(GlobalPretixEthState.chainsRaw.find(chain => chain.chainId === 11155111));
    // const mainnet = chainToWagmiFormat(GlobalPretixEthState.chainsRaw.find(chain => chain.chainId === 1));
    // const optimism = chainToWagmiFormat(GlobalPretixEthState.chainsRaw.find(chain => chain.chainId === 10));
    // const arbitrum = chainToWagmiFormat(GlobalPretixEthState.chainsRaw.find(chain => chain.chainId === 42161));

    const chains = [
        arbitrum,
        arbitrumGoerli,
        mainnet,
        goerli,
        optimism,
        optimismGoerli,
        zkSync,
        sepolia
    ];

    // Wagmi Core Client
    const { provider } = configureChains(chains, [
        walletConnectProvider({
            projectId: "c1b5ad74fb26a47cd04679fb8044eff0",
            version: 2,
            chains
        }),
    ]);

    const wagmiClient = createClient({
        autoConnect: true,
        connectors: modalConnectors({ appName: "web3Modal", chains }),
        provider,
    });

    // Web3Modal and Ethereum Client
    const ethereumClient = new EthereumClient(wagmiClient, chains);

    GlobalPretixEthState.web3Modal = new Web3Modal(
        { projectId: "c1b5ad74fb26a47cd04679fb8044eff0" },
        ethereumClient
    );

    // Switch to user chosen chain before showing modal
    const desiredChainID = GlobalPretixEthState.elements.buttonConnect.getAttribute("data-chain-id");
    const desiredChain = chains.find(chain => chain.id === parseInt(desiredChainID));

    if (desiredChain) {
        GlobalPretixEthState.web3Modal.setSelectedChain(desiredChain);
    }

    let lastAccountStatus = null;

    watchAccount(async (accountState) => {
        // Reload if user disconnects
        if (lastAccountStatus === 'connected' && accountState.status === 'disconnected') {
            location.reload();
        }

        // Detect when sign-in is succesful and automatically proceed to makePayment
        if (lastAccountStatus === 'connecting' && accountState.status === 'connected') {
            try {
                await makePayment();
            } catch (error) {
                showError(error)
            }
        }

        lastAccountStatus = accountState.status;
    });

    let lastNetwork = null;

    watchNetwork(async (network) => {
        // Whenever user switches network, call makePayment again
        if (lastNetwork !== null) {
            try {
                await makePayment();
            } catch (error) {
                showError(error)
            }
        }

        lastNetwork = network.chain.id;
    });

    GlobalPretixEthState.elements.buttonConnect.addEventListener(
        "click",
        async () => {
            try {
                // If user refreshes the page after signing in, the user will still be logged in - we then call makePayment directly
                const alreadySignedIn = await signIn();

                if (alreadySignedIn) makePayment();
            } catch (e) {
                showError(error)
            }
        }
    );
}

window.addEventListener('load', async () => {
    await init();
});
