from django.utils.translation import ugettext_lazy as _
from web3 import Web3
from web3.providers.auto import load_provider_from_uri

from .helpers import evm_like_payment_instructions, token_in_evm_payment_instructions  

ETH = "ETH"
DAI = "DAI"

TOKEN_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


class INetwork(object):
    """Interface that creates basic functionality to plug network into payments.py"""

    identifier = None
    verbose_name = None
    DAI_ADDRESS = None
    eth_currency_choice = ()
    dai_currency_choice = ()

    def __init__(self):
        if not (self.identifier and self.verbose_name):
            raise ValueError(
                "identifier and verbose_name class variable must be specified."
            )
        eth_currency = f"{ETH}-{self.verbose_name}"
        dai_currency = f"{DAI}-{self.verbose_name}"
        self.eth_currency_choice = ((eth_currency, _(eth_currency)),)
        self.dai_currency_choice = ((dai_currency, _(dai_currency)),)

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_ether_or_token, currency_type
    ):
        """
        Instructions on how to pay in this network

        :param wallet_address: address to pay to
        :param payment_amount: amount to pay (in wei)
        :param amount_in_ether_or_token: amount to pay (from_wei(payment_amount))
        :param currency_type: ETH or DAI?
        :returns dictionary with relevant information like
                'erc_681_url', 'uniswap_url', 'web3modal_url',
                'amount_manual' (amount + 'ETH/DAI'), 'wallet_address'
        """

        raise NotImplementedError(
            "This method has not yet been implemented for the network"
        )

    def get_currency_balance(self, hex_wallet_address, rpc_url):
        """
        Get ETH, DAI balance of a wallet in an EVM like network with ETH as base crypto.
        Override this implementation for non EVM like networks or where ETH is a token like DAI.

        :param hex_wallet_address: ethereum wallet address
        :param rpc_url: used to make balance query calls
        :returns tuple with ETH and DAI balance
        """
        w3 = Web3(load_provider_from_uri(rpc_url))
        checksum_address = w3.toChecksumAddress(hex_wallet_address)
        token_contract = w3.eth.contract(abi=TOKEN_ABI, address=self.DAI_ADDRESS)

        eth_amount = w3.eth.getBalance(checksum_address)
        token_amount = token_contract.functions.balanceOf(checksum_address).call()

        return (eth_amount, token_amount)


class Rinkeby(INetwork):
    """Implementation for Rinkeby Testnet"""

    identifier = "Rinkeby"
    verbose_name = "Rinkeby Ethereum Testnet"
    CHAIN_ID = 4
    DAI_ADDRESS = "0xc7AD46e0b8a400Bb3C915120d284AafbA8fc4735"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_ether_or_token, currency_type
    ):
        """
        Instructions for paying ETH or DAI in Rinkeby. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        return evm_like_payment_instructions(wallet_address, payment_amount, currency_type, self.DAI_ADDRESS, self.CHAIN_ID, amount_in_ether_or_token, use_uniswap=True)


class L1(INetwork):
    """Implementation for Ethereum L1"""

    identifier = "L1"
    verbose_name = "Ethereum"
    DAI_ADDRESS = "0x6b175474e89094c44da98b954eedeac495271d0f"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_ether_or_token, currency_type
    ):
        """
        Instructions for paying ETH or DAI in L1 Ethereum. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        return evm_like_payment_instructions(wallet_address, payment_amount, currency_type, self.DAI_ADDRESS, amount_in_ether_or_token=amount_in_ether_or_token, use_uniswap=True)


class KovanOptimism(INetwork):
    """Implementation for Rinkeby Testnet"""

    identifier = "KovanOptimism"
    verbose_name = "Kovan Optimism Testnet"
    CHAIN_ID = 69
    DAI_ADDRESS = "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_ether_or_token, currency_type
    ):
        """
        Instructions for paying ETH or DAI in Kovan on Optimism. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        return evm_like_payment_instructions(wallet_address, payment_amount, currency_type, self.DAI_ADDRESS, self.CHAIN_ID, amount_in_ether_or_token, use_uniswap=True)


class ZkSync(INetwork):
    """Implementation for ZkSync"""

    identifier = "ZkSync"
    verbose_name = "ZkSync"


all_networks = [L1, Rinkeby, KovanOptimism, ZkSync]
all_network_ids_to_networks = {}
all_network_verbose_names_to_ids = {}

for network in all_networks:
    all_network_ids_to_networks[network.identifier] = network()
    all_network_verbose_names_to_ids[network.verbose_name] = network.identifier
