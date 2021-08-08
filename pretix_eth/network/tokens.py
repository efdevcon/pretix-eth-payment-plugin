import decimal

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _

from eth_utils import to_wei
from web3 import Web3
from web3.providers.auto import load_provider_from_uri

from pretix_eth.network.helpers import (
    make_checkout_web3modal_url,
    make_erc_681_url,
    make_uniswap_url,
)


TOKEN_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


class IToken(object):
    NETWORK_IDENTIFIER = None  # E.g. "L1"
    NETWORK_VERBOSE_NAME = None  # E.g. "Ethereum Mainnet"
    TOKEN_SYMBOL = None  # E.g. "ETH"
    TOKEN_VERBOSE_NAME = None  # {TOKEN_SYMBOL}-{NETWORK_VERBOSE_NAME}
    TOKEN_VERBOSE_NAME_TRANSLATED = None  # using django translation module
    # To store in database
    TOKEN_AND_NETWORK_ID_COMBINED = None  # {TOKEN_SYMBOL}-{NETWORK_IDENTIFIER}
    IS_NATIVE_ASSET = True  # Not a token - e.g. ETH in L1.
    ADDRESS = None  # If a token, then the smart contract address.

    def __init__(self):
        self._validate_class_variables()
        self._set_other_token_constants()

    def _validate_class_variables(self):
        if not (
            self.NETWORK_IDENTIFIER and self.NETWORK_VERBOSE_NAME and self.TOKEN_SYMBOL
        ):
            raise ValueError(
                "Please provide network_identifier, verbose name, token symbol for this class"
            )
        if not self.IS_NATIVE_ASSET and not self.ADDRESS:
            raise ValueError(
                "If not native asset (i.e. token), then must provide smart contract address."
            )
        if self.ADDRESS and self.IS_NATIVE_ASSET:
            raise ValueError(
                "If provided smart contract address then make IS_NATIVE_ASSET=False."
            )

    def _set_other_token_constants(self):
        self.TOKEN_VERBOSE_NAME = f"{self.TOKEN_SYMBOL}-{self.NETWORK_VERBOSE_NAME}"
        self.TOKEN_VERBOSE_NAME_TRANSLATED = (
            (self.TOKEN_VERBOSE_NAME, _(self.TOKEN_VERBOSE_NAME)),
        )
        self.TOKEN_AND_NETWORK_ID_COMBINED = (
            f"{self.TOKEN_SYMBOL}-{self.NETWORK_IDENTIFIER}"
        )

    def is_allowed(self, rates: dict, network_ids: set):
        """
        1. Check that there is a key of the format TOKEN_SYMBOL_RATE e.g. ETH_RATE defined in the dictionary rates.
        2. Check that the network is selected."""
        return (self.TOKEN_SYMBOL + "_RATE" in rates) and (
            self.NETWORK_IDENTIFIER in network_ids
        )

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Instructions on how to pay in this network

        :param wallet_address: address to pay to
        :param payment_amount: amount to pay (in wei)
        :param amount_in_token_base_unit: amount to pay (from_wei(payment_amount))
        :returns dictionary with relevant information like
                'erc_681_url', 'uniswap_url', 'web3modal_url',
                'amount_manual' (amount + 'ETH/DAI'), 'wallet_address'
        """
        raise NotImplementedError(
            f"Method not yet implemented for class {self.TOKEN_VERBOSE_NAME}"
        )

    def get_balance_of_address(self, hex_wallet_address, rpc_url):
        """
        Get token/crypto balance of a wallet (default implementation for an EVM like network).

        :param hex_wallet_address: ethereum wallet address
        :param rpc_url: used to make balance query calls
        :returns balance in smallest denomination
        """
        w3 = Web3(load_provider_from_uri(rpc_url))
        checksum_address = w3.toChecksumAddress(hex_wallet_address)

        if self.IS_NATIVE_ASSET:
            return w3.eth.getBalance(checksum_address)
        else:
            token_checksum_address = w3.toChecksumAddress(self.ADDRESS)
            token_contract = w3.eth.contract(
                abi=TOKEN_ABI, address=token_checksum_address
            )
            return token_contract.functions.balanceOf(checksum_address).call()


""" Rinkeby L1 Network """


class RinkebyL1(IToken):
    NETWORK_IDENTIFIER = "Rinkeby"
    NETWORK_VERBOSE_NAME = "Rinkeby Ethereum Testnet"
    CHAIN_ID = 4


class EthRinkebyL1(RinkebyL1):
    TOKEN_SYMBOL = "ETH"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Instructions for paying ETH on Rinkeby. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(wallet_address, payment_amount, self.CHAIN_ID)
        uniswap_url = make_uniswap_url(
            self.TOKEN_SYMBOL, wallet_address, amount_in_token_base_unit
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(
            self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address, self.CHAIN_ID
        )

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }


class DaiRinkebyL1(RinkebyL1):
    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0xc7AD46e0b8a400Bb3C915120d284AafbA8fc4735"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Instructions for paying DAI on Rinkeby. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(
            wallet_address,
            payment_amount,
            self.CHAIN_ID,
            is_token=True,
            token_address=self.ADDRESS,
        )
        uniswap_url = make_uniswap_url(
            self.ADDRESS, wallet_address, amount_in_token_base_unit
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(
            self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address, self.CHAIN_ID
        )

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }


""" Ethereum L1 Mainnet network """


class L1(IToken):
    NETWORK_IDENTIFIER = "L1"
    NETWORK_VERBOSE_NAME = "Ethereum Mainnet"


class EthL1(L1):
    TOKEN_SYMBOL = "ETH"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Instructions for paying ETH on L1. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(wallet_address, payment_amount)
        uniswap_url = make_uniswap_url(
            self.TOKEN_SYMBOL, wallet_address, amount_in_token_base_unit
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(
            self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address
        )

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }


class DaiL1(L1):
    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0x6b175474e89094c44da98b954eedeac495271d0f"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Instructions for paying DAI on L1. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(
            wallet_address, payment_amount, is_token=True, token_address=self.ADDRESS
        )
        uniswap_url = make_uniswap_url(
            self.ADDRESS, wallet_address, amount_in_token_base_unit
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(
            self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address
        )

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }


""" Optimism Kovan Network """

registry = [EthRinkebyL1(), DaiRinkebyL1(), EthL1(), DaiL1()]
all_network_verbose_names_to_ids = {}
for token in registry:
    if not token.NETWORK_VERBOSE_NAME in all_network_verbose_names_to_ids:
        all_network_verbose_names_to_ids[
            token.NETWORK_VERBOSE_NAME
        ] = token.NETWORK_IDENTIFIER

all_token_verbose_names_to_tokens = {}
all_token_and_network_ids_to_tokens = {}
for token in registry:
    all_token_verbose_names_to_tokens[token.TOKEN_VERBOSE_NAME] = token
    all_token_and_network_ids_to_tokens[token.TOKEN_AND_NETWORK_ID_COMBINED] = token


def token_verbose_name_to_token_network_id(verbose_name):
    """E.g. "ETH-Ethereum Mainnet" to "ETH-L1". Fails if token not there"""
    if not verbose_name in all_token_verbose_names_to_tokens:
        raise ValueError(
            f"Token verbose name not registered in registry - {verbose_name}"
        )
    token: IToken = all_token_verbose_names_to_tokens[verbose_name]
    return token.TOKEN_AND_NETWORK_ID_COMBINED
