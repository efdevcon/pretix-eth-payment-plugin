import pytest
from pretix_eth.network.tokens import (
    IToken,
    registry,
    all_token_and_network_ids_to_tokens,
    all_token_verbose_names_to_tokens,
)


def assert_error_when_init_variables_not_passed(Test: IToken):
    with pytest.raises(Exception) as execinfo:
        Test()
    assert (
        execinfo.value.args[0]
        == "Please provide network_identifier, verbose name, token symbol for this class"
    )


def test_error_if_no_network_constants_not_set():
    class Test(IToken):
        pass

    assert_error_when_init_variables_not_passed(Test)


def test_error_if_some_network_constants_not_set():
    # Network ID, but no network verbose name, token symbol
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"

    assert_error_when_init_variables_not_passed(Test)

    # Network ID and token symbol but no network verbose name,
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        TOKEN_SYMBOL = "T"

    assert_error_when_init_variables_not_passed(Test)

    # Network ID and network verbose name, but no token symbol
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        NETWORK_VERBOSE_NAME = "Test Network"

    assert_error_when_init_variables_not_passed(Test)


def test_network_creation_when_basic_constants_set():
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        NETWORK_VERBOSE_NAME = "Test Network"
        TOKEN_SYMBOL = "T"

    try:
        testToken = Test()
        assert (
            testToken.TOKEN_VERBOSE_NAME
            == testToken.TOKEN_SYMBOL + " - " + testToken.NETWORK_VERBOSE_NAME
        )
        assert (
            testToken.TOKEN_AND_NETWORK_ID_COMBINED
            == testToken.TOKEN_SYMBOL + " - " + testToken.NETWORK_IDENTIFIER
        )
    except Exception:
        pytest.fail("Should not throw an error")


def test_token_init_address_and_native_asset_setup():
    # Token Address defined but native asset also set to true:
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        NETWORK_VERBOSE_NAME = "Test Network"
        TOKEN_SYMBOL = "T"
        ADDRESS = "0xsmth"
        IS_NATIVE_ASSET = True

    with pytest.raises(Exception):
        Test()

    # Not native asset but also no token address specified.
    class Test(IToken):
        NETWORK_IDENTIFIER = "Test"
        NETWORK_VERBOSE_NAME = "Test Network"
        TOKEN_SYMBOL = "T"
        ADDRESS = None
        IS_NATIVE_ASSET = False

    with pytest.raises(Exception):
        Test()


def test_all_token_and_network_ids_to_tokens_is_correctly_set():
    assert len(all_token_and_network_ids_to_tokens) == len(registry)
    for token in registry:
        assert (
            token.TOKEN_AND_NETWORK_ID_COMBINED in all_token_and_network_ids_to_tokens
        )
        assert (
            all_token_and_network_ids_to_tokens[token.TOKEN_AND_NETWORK_ID_COMBINED]
            == token
        )


def test_all_token_verbose_names_to_tokens_is_correctly_set():
    assert len(all_token_verbose_names_to_tokens) == len(registry)
    for token in registry:
        assert token.TOKEN_VERBOSE_NAME in all_token_verbose_names_to_tokens
        assert all_token_verbose_names_to_tokens[token.TOKEN_VERBOSE_NAME] == token
