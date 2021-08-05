from django.utils.translation import ugettext_lazy as _

from pretix_eth.network.helpers import make_checkout_web3modal_url, make_erc_681_url, make_uniswap_url


class IToken(object):
    NETWORK_IDENTIFIER = None
    NETWORK_VERBOSE_NAME = None
    TOKEN_SYMBOL = None
    TOKEN_VERBOSE_NAME = None
    TOKEN_VERBOSE_NAME_TRANSLATED = None

    def __init__(self):
        if not (self.NETWORK_IDENTIFIER and self.NETWORK_VERBOSE_NAME and self.TOKEN_SYMBOL):
            raise ValueError("Please provide network_identifier, verbose name, token symbol for this class")
        self.TOKEN_VERBOSE_NAME = f"{self.TOKEN_SYMBOL}-{self.NETWORK_VERBOSE_NAME}"
        self.TOKEN_VERBOSE_NAME_TRANSLATED = ((self.TOKEN_VERBOSE_NAME, _(self.TOKEN_VERBOSE_NAME)),)

    def is_allowed(self, rates: dict):
        """ Check that there is a key of the format TOKEN_SYMBOL_RATE e.g. ETH_RATE defined in the dictionary rates. """
        return (self.TOKEN_SYMBOL+"_RATE" in rates)

    def payment_instructions(self, wallet_address, payment_amount, amount_in_token_base_unit):
        raise NotImplementedError(f"Method not yet implemented for class {self.TOKEN_VERBOSE_NAME}")

""" Rinkeby L1 Network """

class RinkebyL1(IToken):
    NETWORK_IDENTIFIER = "Rinkeby"
    NETWORK_VERBOSE_NAME = "Rinkeby Ethereum Testnet"
    CHAIN_ID = 4 

class EthRinkebyL1(RinkebyL1):
    TOKEN_SYMBOL = "ETH"
    def payment_instructions(self, wallet_address, payment_amount, amount_in_token_base_unit):
        """
        Instructions for paying ETH on Rinkeby. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(wallet_address, payment_amount, self.CHAIN_ID)
        uniswap_url = make_uniswap_url(self.TOKEN_SYMBOL, wallet_address, amount_in_token_base_unit)
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address, self.CHAIN_ID)

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }

class DaiRinkebyL1(RinkebyL1):
    TOKEN_SYMBOL = "DAI"
    ADDRESS = "0xc7AD46e0b8a400Bb3C915120d284AafbA8fc4735"

    def payment_instructions(self, wallet_address, payment_amount, amount_in_token_base_unit):
        """
        Instructions for paying DAI on Rinkeby. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(wallet_address,payment_amount,self.CHAIN_ID,is_token=True,token_address=self.ADDRESS)
        uniswap_url = make_uniswap_url(self.ADDRESS, wallet_address, amount_in_token_base_unit
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address, self.CHAIN_ID)

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
    def payment_instructions(self, wallet_address, payment_amount, amount_in_token_base_unit):
        """
        Instructions for paying ETH on L1. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(wallet_address, payment_amount)
        uniswap_url = make_uniswap_url(self.TOKEN_SYMBOL, wallet_address, amount_in_token_base_unit)
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address)

        return {
            "erc_681_url": erc_681_url,
            "uniswap_url": uniswap_url,
            "web3modal_url": web3modal_url,
            "amount_manual": amount_manual,
            "wallet_address": wallet_address,
        }

class DaiL1(L1):
    TOKEN_SYMBOL = "DAI"
    ADDRESS = "0x6b175474e89094c44da98b954eedeac495271d0f"

    def payment_instructions(self, wallet_address, payment_amount, amount_in_token_base_unit):
        """
        Instructions for paying DAI on L1. Pay via a web3 modal, ERC 681 (QR Code), uniswap url or manually.
        """
        erc_681_url = make_erc_681_url(wallet_address,payment_amount,is_token=True,token_address=self.ADDRESS)
        uniswap_url = make_uniswap_url(self.ADDRESS, wallet_address, amount_in_token_base_unit
        )
        amount_manual = f"{amount_in_token_base_unit} {self.TOKEN_SYMBOL}"
        web3modal_url = make_checkout_web3modal_url(self.TOKEN_SYMBOL, amount_in_token_base_unit, wallet_address)

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
        all_network_verbose_names_to_ids[token.NETWORK_VERBOSE_NAME] = token.NETWORK_IDENTIFIER

