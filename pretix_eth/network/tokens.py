from typing import Optional
import decimal

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from eth_utils import to_wei
from web3 import Web3
from web3.providers.auto import load_provider_from_uri

from pretix_eth.network.helpers import (
    make_checkout_web3modal_url,
    make_erc_681_url,
    make_uniswap_url,
    get_eth_price_from_external_apis
)

TOKEN_ABI = [
    # Functions
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    # Event
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "from",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "to",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "value",
                "type": "uint256",
            },
        ],
        "name": "Transfer",
        "type": "event",
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
    EIP3091_EXPLORER_URL = None  # if set, allows links to transactions to be generated
    CHAIN_ID = None
    DISABLED = False

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
        self.TOKEN_VERBOSE_NAME = f"{self.TOKEN_SYMBOL} - {self.NETWORK_VERBOSE_NAME}"
        self.TOKEN_VERBOSE_NAME_TRANSLATED = (
            (self.TOKEN_VERBOSE_NAME, _(self.TOKEN_VERBOSE_NAME)),
        )
        self.TOKEN_AND_NETWORK_ID_COMBINED = (
            f"{self.TOKEN_SYMBOL} - {self.NETWORK_IDENTIFIER}"
        )

    def is_allowed(self, rates: dict, network_ids: set):
        """
        1. Check that there is a key of the format TOKEN_SYMBOL_RATE
        e.g. ETH_RATE defined in the dictionary rates.
        2. Check that the network is selected."""
        return (self.TOKEN_SYMBOL + "_RATE" in rates) and (
            self.NETWORK_IDENTIFIER in network_ids
        ) and not self.DISABLED

    def get_ticket_price_in_token(self, total, rates, fiat_currency):
        if not (self.TOKEN_SYMBOL + "_RATE" in rates):
            raise ImproperlyConfigured(
                f"Token Symbol not defined in TOKEN_RATES admin settings: {self.TOKEN_SYMBOL}"
            )

        chosen_currency_rate = decimal.Decimal(rates[self.TOKEN_SYMBOL + "_RATE"])

        # We can't dynamically fetch arbitrary fiat currencies as we have to ensure the exchange apis support them - we support EUR and USD for now  # noqa: E501
        # Fall back to the manually set price in this case
        if (self.TOKEN_SYMBOL == 'ETH' and (fiat_currency == 'USD' or fiat_currency == 'EUR')):
            # If token is ETH, fetch the price from external apis -
            # if this fails for some reason (endpoints down, unreliable results, etc.), use the manually set price instead  # noqa: E501
            eth_price = get_eth_price_from_external_apis(fiat_currency)

            if (eth_price is not None):
                chosen_currency_rate = decimal.Decimal(eth_price)

        rounding_base = decimal.Decimal("1.00000")
        rounded_price = (total / chosen_currency_rate).quantize(rounding_base)
        final_price = to_wei(rounded_price, "ether")

        return final_price, chosen_currency_rate.quantize(rounding_base)

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

    def get_transaction_link(self, transaction_hash: Optional[str]) -> Optional[str]:
        return "{base}/tx/{hash}".format(
            base=self.EIP3091_EXPLORER_URL,
            hash=transaction_hash,
        )

    def get_address_link(self, address: Optional[str]) -> Optional[str]:
        return "{base}/address/{address}".format(
            base=self.EIP3091_EXPLORER_URL,
            address=address,
        )


""" L1 Networks """


class L1(IToken):
    NETWORK_IDENTIFIER = "L1"
    NETWORK_VERBOSE_NAME = "Ethereum Mainnet"
    CHAIN_ID = 1
    EIP3091_EXPLORER_URL = "https://etherscan.io"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Generic instructions for paying on all L1 networks (eg Goerli and Mainnet),
        both for native tokens and custom tokens.

        Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(
            to_address=wallet_address,
            payment_amount=payment_amount,
            chain_id=self.CHAIN_ID,
            is_token=not self.IS_NATIVE_ASSET,
            token_address=self.ADDRESS,
        )
        uniswap_url = make_uniswap_url(
            output_currency=self.TOKEN_SYMBOL if self.IS_NATIVE_ASSET else self.ADDRESS,
            recipient_address=wallet_address,
            exact_amount=amount_in_token_base_unit,
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(
            currency_type=self.TOKEN_SYMBOL,
            amount_in_ether_or_token=amount_in_token_base_unit,
            wallet_address=wallet_address,
            chainId=self.CHAIN_ID,
        )

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }


class GoerliL1(L1):
    """
    Constants for Goerli Ethereum Testnet
    """

    NETWORK_IDENTIFIER = "Goerli"
    NETWORK_VERBOSE_NAME = "Goerli Ethereum Testnet"
    CHAIN_ID = 5
    EIP3091_EXPLORER_URL = "https://goerli.etherscan.io"


class EthGoerliL1(GoerliL1):
    """
    Ethereum on Goerli L1 Network
    """

    TOKEN_SYMBOL = "ETH"


class DaiGoerliL1(GoerliL1):
    """
    DAI on Goerli L1 Network
    """

    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0xdc31Ee1784292379Fbb2964b3B9C4124D8F89C60"


class EthL1(L1):
    """
    Ethereum on Mainnet L1 Network
    """

    TOKEN_SYMBOL = "ETH"


class DaiL1(L1):
    """
    DAI on Mainnet L1 Network
    """

    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"


""" Optimism Networks """


class Optimism(L1):
    """
    Constants for the Optimism Mainnet
    """

    NETWORK_IDENTIFIER = "Optimism"
    NETWORK_VERBOSE_NAME = "Optimism Mainnet"
    CHAIN_ID = 10
    EIP3091_EXPLORER_URL = "https://optimistic.etherscan.io"


class EthOptimism(Optimism):
    """
    Ethereum on Optimism Mainnet
    """

    TOKEN_SYMBOL = "ETH"


class DaiOptimism(Optimism):
    """
    DAI on Optimism Mainnet
    """

    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"


class ETHGoerliOptimism(Optimism):
    """
    Ethereum on Optimism Goerli Network
    """

    TOKEN_SYMBOL = "ETH"
    NETWORK_IDENTIFIER = "GoerliOptimism"
    NETWORK_VERBOSE_NAME = "Goerli Optimism Testnet"
    CHAIN_ID = 420
    EIP3091_EXPLORER_URL = "https://goerli-optimism.etherscan.io"


class DaiGoerliOptimism(Optimism):
    """
    Dai on Optimism Goerli Network
    """

    TOKEN_SYMBOL = "DAI"
    NETWORK_IDENTIFIER = "GoerliOptimism"
    NETWORK_VERBOSE_NAME = "Goerli Optimism Testnet"
    CHAIN_ID = 420
    EIP3091_EXPLORER_URL = "https://goerli-optimism.etherscan.io"


""" Arbitrum Networks """


class Arbitrum(L1):
    """
    Implementation for Arbitrum networks
    """

    NETWORK_IDENTIFIER = "Arbitrum"
    NETWORK_VERBOSE_NAME = "Arbitrum Mainnet"
    CHAIN_ID = 42161
    EIP3091_EXPLORER_URL = "https://explorer.arbitrum.io"

    def payment_instructions(
        self, wallet_address, payment_amount, amount_in_token_base_unit
    ):
        """
        Generic instructions for paying on all Arbitrum networks (eg Goerli and Mainnet),
        both for native tokens and custom tokens.

        Pay via a web3 modal, ERC 681 (QR Code) or manually.
        """
        erc_681_url = make_erc_681_url(
            to_address=wallet_address,
            payment_amount=payment_amount,
            chain_id=self.CHAIN_ID,
            is_token=not self.IS_NATIVE_ASSET,
            token_address=self.ADDRESS,
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(
            currency_type=self.TOKEN_SYMBOL,
            amount_in_ether_or_token=amount_in_token_base_unit,
            wallet_address=wallet_address,
            chainId=self.CHAIN_ID,
        )

        return {
            "erc_681_url": erc_681_url,
            # "uniswap_url": None,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }


class ETHArbitrum(Arbitrum):
    """
    Ethereum on Arbitrum mainnet Network
    """

    TOKEN_SYMBOL = "ETH"


class DaiArbitrum(Arbitrum):
    """
    DAI on Arbitrum Mainnet
    """

    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"


class ETHGoerliArbitrum(Arbitrum):
    """
    Ethereum on Arbitrum Goerli Network
    """

    TOKEN_SYMBOL = "ETH"
    NETWORK_IDENTIFIER = "GoerliArbitrum"
    NETWORK_VERBOSE_NAME = "Goerli Arbitrum Testnet"
    CHAIN_ID = 421613
    EIP3091_EXPLORER_URL = "https://goerli.arbiscan.io"


class DaiGoerliArbitrum(Arbitrum):
    """
    Dai on Arbitrum Goerli Network
    """

    TOKEN_SYMBOL = "DAI"
    NETWORK_IDENTIFIER = "GoerliArbitrum"
    NETWORK_VERBOSE_NAME = "Goerli Arbitrum Testnet"
    CHAIN_ID = 421613
    EIP3091_EXPLORER_URL = "https://goerli.arbiscan.io"


# """ Polygon zk evm """
class Polygon(L1):
    """
    Implementation for ZkSync networks
    """

    NETWORK_IDENTIFIER = "PolygonZkEVM"
    NETWORK_VERBOSE_NAME = "Polygon zkEVM"
    CHAIN_ID = 1101
    EIP3091_EXPLORER_URL = "https://zkevm.polygonscan.com/"


class ETHPolygonZkEvm(Polygon):
    """
    Ethereum on Polygon mainnet Network
    """

    TOKEN_SYMBOL = "ETH"


class DaiPolygonZkEvm(Polygon):
    """
    DAI on Polygon Mainnet
    """

    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0xC5015b9d9161Dca7e18e32f6f25C4aD850731Fd4"


# """ ZkSync Networks """
class ZkSync(L1):
    """
    Implementation for ZkSync networks
    """

    NETWORK_IDENTIFIER = "ZkSync"
    NETWORK_VERBOSE_NAME = "ZkSync Mainnet"
    CHAIN_ID = 324
    EIP3091_EXPLORER_URL = "https://explorer.zksync.io"


class ETHZkSync(ZkSync):
    """
    Ethereum on ZkSync mainnet Network
    """

    TOKEN_SYMBOL = "ETH"


class DaiZkSync(ZkSync):
    """
    DAI on ZkSync Mainnet
    """

    TOKEN_SYMBOL = "DAI"
    IS_NATIVE_ASSET = False
    ADDRESS = "0x6b175474e89094c44da98b954eedeac495271d0f"


registry = [
    EthL1(),
    DaiL1(),
    EthGoerliL1(),
    DaiGoerliL1(),
    EthOptimism(),
    DaiOptimism(),
    ETHGoerliOptimism(),
    DaiGoerliOptimism(),
    ETHArbitrum(),
    DaiArbitrum(),
    ETHGoerliArbitrum(),
    DaiGoerliArbitrum(),
    ETHZkSync(),
    ETHPolygonZkEvm(),
    DaiPolygonZkEvm()
]
all_network_verbose_names_to_ids = {}
for token in registry:
    if token.NETWORK_VERBOSE_NAME not in all_network_verbose_names_to_ids:
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
    if verbose_name not in all_token_verbose_names_to_tokens:
        raise ValueError(
            f"Token verbose name not registered in registry - {verbose_name}"
        )
    token: IToken = all_token_verbose_names_to_tokens[verbose_name]
    return token.TOKEN_AND_NETWORK_ID_COMBINED
