from django.core.exceptions import ImproperlyConfigured
import pytest
from pretix_eth.network.tokens import IToken
from pretix_eth.network import helpers

# get_ticket_price_in_token, is_allowed, helpers, tokenL1, tokenL2, ativeL1 nativeL2
def create_token():
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        NETWORK_VERBOSE_NAME = "Test Network"
        TOKEN_SYMBOL = "T"
        CHAIN_ID = 1

    return Test()


def test_token_get_ticket_price_in_token_is_correct():
    test_token: IToken = create_token()
    price_in_token_weis = test_token.get_ticket_price_in_token(10, {"T_RATE": 1000})
    # price of 1 T token = 1000. So 10$ = 0.001 T tokens or 10^16.
    assert price_in_token_weis == 10000000000000000


def test_token_get_price_in_token_gives_error_if_no_rate_given():
    test_token: IToken = create_token()
    with pytest.raises(ImproperlyConfigured) as execinfo:
        test_token.get_ticket_price_in_token(10, {"ANOTHER_TOKEN_RATE": 1000})
    assert (
        execinfo.value.args[0]
        == "Token Symbol not defined in TOKEN_RATES admin settings: T"
    )


# TODO Test IToken.is_allowed()


def test_make_erc_681_url_for_native_asset():
    to_address = "0xtest1"
    payment_amount = "10"
    chain_id = 3

    erc681_url = helpers.make_erc_681_url(to_address, payment_amount, chain_id)
    assert erc681_url == f"ethereum:{to_address}@{chain_id}?value={payment_amount}"


def test_make_erc_681_url_for_token():
    to_address = "0xtest1"
    payment_amount = "10"
    chain_id = 3
    is_token = True
    token_address = "0xtoken"

    erc681_url = helpers.make_erc_681_url(
        to_address, payment_amount, chain_id, is_token, token_address
    )
    assert (
        erc681_url
        == f"ethereum:{token_address}@{chain_id}/transfer?address={to_address}&uint256={payment_amount}"
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


# helpers.uniswap, web3modal-checkout links.
