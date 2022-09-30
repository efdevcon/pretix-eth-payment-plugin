from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
import pytest

TEST_ETH_RATE = "4000.0"
TEST_DAI_RATE = "1.0"
FORM_FIELDS_SETTINGS = ("TOKEN_RATES", "_NETWORKS", "NETWORK_RPC_URL")


@pytest.mark.django_db
def test_provider_properties(provider):
    assert provider.identifier == "ethereum"
    assert provider.verbose_name == "ETH or DAI"
    assert provider.public_name == "ETH or DAI"


@pytest.mark.django_db
def test_provider_settings_form_fields(provider):
    form_fields = provider.settings_form_fields
    for field in FORM_FIELDS_SETTINGS:
        assert field in form_fields


@pytest.mark.django_db
def test_provider_is_allowed(event, provider):
    for setting in FORM_FIELDS_SETTINGS:
        assert provider.settings.get(setting) is None

    factory = RequestFactory()

    session = SessionStore()
    session.create()

    request = factory.get("/checkout")
    request.event = event
    request.session = session

    # test that incorrect settings lead to provider being disallowed.
    provider.settings.set("TOKEN_RATES", dict())
    provider.settings.set("_NETWORKS", [])
    provider.settings.set("NETWORK_RPC_URL", dict())
    provider.settings.set("SINGLE_RECEIVER_ADDRESS",
                          "0x0000000000000000000000000000000000000000")
    assert not provider.is_allowed(request)

    # now test with right values:
    provider.settings.set("TOKEN_RATES", {"ETH_RATE": TEST_ETH_RATE})
    provider.settings.set("_NETWORKS", ["L1"])
    provider.settings.set(
        "NETWORK_RPC_URL",
        {"L1_RPC_URL": "https://mainnet.infura.io/v3/somekeyvaluehere"},
    )
    assert provider.is_allowed(request)


@pytest.mark.django_db
def test_provider_payment_form_fields_only_ETH_L1(provider):
    provider.settings.set("TOKEN_RATES", {"ETH_RATE": TEST_ETH_RATE})
    provider.settings.set("_NETWORKS", ["L1"])

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields["currency_type"]

    assert len(currency_type_field.choices) == 1
    assert currency_type_field.choices[0][0] == "ETH - Ethereum Mainnet"


@pytest.mark.django_db
def test_provider_payment_form_fields_only_DAI_L1(provider):
    provider.settings.set("TOKEN_RATES", {"DAI_RATE": TEST_DAI_RATE})
    provider.settings.set("_NETWORKS", ["L1"])

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields["currency_type"]

    assert len(currency_type_field.choices) == 1
    assert currency_type_field.choices[0][0] == "DAI - Ethereum Mainnet"


@pytest.mark.django_db
def test_provider_payment_form_fields_multiple_networks_single_currency(provider):
    provider.settings.set("TOKEN_RATES", {"DAI_RATE": TEST_DAI_RATE})
    provider.settings.set("_NETWORKS", ["L1", "Rinkeby", "KovanOptimism"])

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields["currency_type"]

    assert len(currency_type_field.choices) == 3
    assert currency_type_field.choices[0][0] == "DAI - Ethereum Mainnet"
    assert currency_type_field.choices[1][0] == "DAI - Rinkeby Ethereum Testnet"
    assert currency_type_field.choices[2][0] == "DAI - Kovan Optimism Testnet"


@pytest.mark.django_db
def test_provider_payment_form_fields_multiple_networks_multiple_currencies(provider):
    provider.settings.set(
        "TOKEN_RATES", {"ETH_RATE": TEST_ETH_RATE, "DAI_RATE": TEST_DAI_RATE}
    )
    provider.settings.set("_NETWORKS", ["L1", "Rinkeby", "RinkebyArbitrum"])

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields["currency_type"]

    assert len(currency_type_field.choices) == 5
    assert currency_type_field.choices[0][0] == "ETH - Ethereum Mainnet"
    assert currency_type_field.choices[1][0] == "DAI - Ethereum Mainnet"
    assert currency_type_field.choices[2][0] == "ETH - Rinkeby Ethereum Testnet"
    assert currency_type_field.choices[3][0] == "DAI - Rinkeby Ethereum Testnet"
    assert currency_type_field.choices[4][0] == "ETH - Rinkeby Arbitrum Testnet"


@pytest.mark.django_db
def test_provider_payment_form_fields_adding_extra_network_doesnt_fail(provider):
    provider.settings.set("TOKEN_RATES", {"ETH_RATE": TEST_ETH_RATE})
    provider.settings.set("_NETWORKS", ["L1", "KovanArbitrum"])

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields["currency_type"]

    assert len(currency_type_field.choices) == 1
    assert currency_type_field.choices[0][0] == "ETH - Ethereum Mainnet"


@pytest.mark.django_db
def test_provider_payment_form_fields_adding_extra_currency_doesnt_fail(provider):
    provider.settings.set("TOKEN_RATES", {"ETH_RATE": TEST_ETH_RATE, "UNI_RATE": 100})
    provider.settings.set("_NETWORKS", ["L1"])

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields["currency_type"]

    assert len(currency_type_field.choices) == 1
    assert currency_type_field.choices[0][0] == "ETH - Ethereum Mainnet"
