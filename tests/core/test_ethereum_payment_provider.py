from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore

import pytest


ETH_ADDRESS = '0xeee0123400000000000000000000000000000000'
DAI_ADDRESS = '0xda10123400000000000000000000000000000000'


@pytest.mark.django_db
def test_provider_properties(provider):
    assert provider.identifier == 'ethereum'
    assert provider.verbose_name == 'Ethereum'
    assert provider.public_name == 'Ethereum'


@pytest.mark.django_db
def test_provider_settings_form_fields(provider):
    form_fields = provider.settings_form_fields

    assert 'ETH' in form_fields
    assert 'DAI' in form_fields
    assert 'TRANSACTION_PROVIDER' in form_fields
    assert 'TOKEN_PROVIDER' in form_fields


@pytest.mark.parametrize(
    'ETH,DAI',
    (
        (None, None),
        (ETH_ADDRESS, None),
        (None, DAI_ADDRESS),
        (ETH_ADDRESS, DAI_ADDRESS),
    )
)
@pytest.mark.django_db
def test_provider_is_allowed(event, provider, ETH, DAI):  # noqa: N803
    # pre-check that ETH and DAI settings are null and not allowed without configuration
    assert provider.settings.ETH is None
    assert provider.settings.DAI is None

    factory = RequestFactory()
    session = SessionStore()
    session.create()
    request = factory.get('/checkout')
    request.event = event
    request.session = session

    assert provider.is_allowed(request) is False

    if ETH is not None:
        provider.settings.set('ETH', ETH)
    if DAI is not None:
        provider.settings.set('DAI', DAI)

    expected = ETH is not None or DAI is not None

    assert provider.is_allowed(request) is expected


@pytest.mark.django_db
def test_provider_payment_form_fields_improper_configuration(provider):
    with pytest.raises(ImproperlyConfigured):
        provider.payment_form_fields


@pytest.mark.django_db
def test_provider_payment_form_fields_only_ETH(provider):
    provider.settings.set('ETH', ETH_ADDRESS)

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields['currency_type']
    assert len(currency_type_field.choices) == 1
    choice = currency_type_field.choices[0]
    assert choice[0] == 'ETH'


@pytest.mark.django_db
def test_provider_payment_form_fields_only_DAI(provider):
    provider.settings.set('DAI', DAI_ADDRESS)

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields['currency_type']
    assert len(currency_type_field.choices) == 1
    choice = currency_type_field.choices[0]
    assert choice[0] == 'DAI'


@pytest.mark.django_db
def test_provider_payment_form_fields_both_ETH_and_DAI(provider):
    provider.settings.set('DAI', DAI_ADDRESS)
    provider.settings.set('ETH', ETH_ADDRESS)

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields['currency_type']
    assert len(currency_type_field.choices) == 2
    dai_choice = currency_type_field.choices[0]
    eth_choice = currency_type_field.choices[1]
    assert dai_choice[0] == 'DAI'
    assert eth_choice[0] == 'ETH'
