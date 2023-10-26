from django.core.exceptions import ImproperlyConfigured
import pytest
from pretix_eth.network.tokens import IToken
from pretix_eth.network import helpers


def create_token():
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        NETWORK_VERBOSE_NAME = "Test Network"
        TOKEN_SYMBOL = "T"
        CHAIN_ID = 1

    return Test()


def test_if_token_is_allowed():
    test_token: IToken = create_token()
    # allowed only if both SYMBOL_RATE and NETWORK_IDENTIFIER exist.
    assert test_token.is_allowed({"T_RATE": 1000}, {"Test", "Another"})
    assert not test_token.is_allowed({"A_RATE": 1000}, {"Test", "Another"})
    assert not test_token.is_allowed({"T_RATE": 1000}, {"Another"})


def test_token_get_ticket_price_in_token_is_correct():
    test_token: IToken = create_token()
    price_in_token_weis, _ = test_token.get_ticket_price_in_token(
        10, {"T_RATE": 1000}, 'SOME_FIAT_CURRENCY')
    # price of 1 T token = 1000. So 10$ = 0.001 T tokens or 10^16.
    assert price_in_token_weis == 10000000000000000


def test_token_get_price_in_token_gives_error_if_no_rate_given():
    test_token: IToken = create_token()
    with pytest.raises(ImproperlyConfigured) as execinfo:
        test_token.get_ticket_price_in_token(10, {"ANOTHER_TOKEN_RATE": 1000}, 'SOME_FIAT_CURRENCY')
    assert (
        execinfo.value.args[0]
        == "Token Symbol not defined in TOKEN_RATES admin settings: T"
    )


def test_make_erc_681_url_for_token_fails_if_no_addres_specified():
    to_address = "0xtest1"
    payment_amount = "10"
    chain_id = 3
    is_token = True
    token_address = None

    with pytest.raises(ValueError) as execinfo:
        helpers.make_erc_681_url(
            to_address, payment_amount, chain_id, is_token, token_address
        )
    assert (
        execinfo.value.args[0]
        == "if is_token is true, then you must pass contract address of the token."
    )


def test_erc_681_url_for_L1():
    """Test for both native asset and token"""
    # for native asset
    erc681_url = helpers.make_erc_681_url("0xtest1", "10")
    assert erc681_url == "ethereum:0xtest1?value=10"

    # for token
    erc681_url = helpers.make_erc_681_url(
        "0xtest1", "10", is_token=True, token_address="0xtoken"
    )
    assert erc681_url == "ethereum:0xtoken/transfer?address=0xtest1&uint256=10"


def test_make_erc_681_url_for_L2():
    """Test for both native asset and token"""
    # for native asset
    erc681_url = helpers.make_erc_681_url("0xtest1", "10", chain_id=3)
    assert erc681_url == "ethereum:0xtest1@3?value=10"

    # for token
    erc681_url = helpers.make_erc_681_url(
        "0xtest1", "10", chain_id=3, is_token=True, token_address="0xtoken"
    )
    assert erc681_url == "ethereum:0xtoken@3/transfer?address=0xtest1&uint256=10"


def test_uniswap_link():
    uniswap_link = helpers.make_uniswap_url("ETH", "0xtest1", 1000)
    assert (
        uniswap_link
        == "https://uniswap.exchange/send?exactField=output&exactAmount=1000&outputCurrency=ETH&recipient=0xtest1"  # noqa: E501
    )


def test_web3modal_checkout_link():
    web3modal_checkout_link = helpers.make_checkout_web3modal_url(
        "ETH", 10000, "0xtest1"
    )
    assert (
        web3modal_checkout_link
        == "https://checkout.web3modal.com/?currency=ETH&amount=10000&to=0xtest1&chainId=1"
    )


def test_web3modal_checkout_link_works_only_ETH_and_DAI():
    with pytest.raises(ValueError) as execinfo:
        helpers.make_checkout_web3modal_url("TEST", 10000, "0xtest1")
        assert execinfo.value.args[0] == "currency_type should be either ETH or DAI"
