from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore

import pytest


TEST_ETH_RATE = '0.004'
TEST_DAI_RATE = '1.0'
TEST_WALLET_ADDRESS = '0x0000000000000000000000000000000000000000'


@pytest.mark.django_db
def test_provider_properties(provider):
    assert provider.identifier == 'ethereum'
    assert provider.verbose_name == 'Ethereum'
    assert provider.public_name == 'Ethereum'


@pytest.mark.django_db
def test_provider_settings_form_fields(provider):
    form_fields = provider.settings_form_fields

    assert 'WALLET_ADDRESS' in form_fields
    assert 'ETH_RATE' in form_fields
    assert 'xDAI_RATE' in form_fields
    assert 'TRANSACTION_PROVIDER' in form_fields
    assert 'TOKEN_PROVIDER' in form_fields


@pytest.mark.django_db
def test_provider_is_allowed(event, provider):
    assert provider.settings.WALLET_ADDRESS is None
    assert provider.settings.ETH_RATE is None
    assert provider.settings.xDAI_RATE is None

    factory = RequestFactory()

    session = SessionStore()
    session.create()

    request = factory.get('/checkout')
    request.event = event
    request.session = session

    assert not provider.is_allowed(request)

    provider.settings.set('WALLET_ADDRESS', TEST_WALLET_ADDRESS)

    assert not provider.is_allowed(request)

    provider.settings.set('ETH_RATE', TEST_ETH_RATE)

    assert not provider.is_allowed(request)

    provider.settings.set('xDAI_RATE', TEST_DAI_RATE)

    assert provider.is_allowed(request)


@pytest.mark.django_db
def test_provider_payment_form_fields_improper_configuration(provider):
    with pytest.raises(ImproperlyConfigured):
        provider.payment_form_fields


@pytest.mark.django_db
def test_provider_payment_form_fields(provider):
    payment_form_fields = provider.payment_form_fields

    currency_type_field = payment_form_fields['currency_type']

    assert len(currency_type_field.choices) == 2

    assert currency_type_field.choices[0][0] == 'DAI'
    assert currency_type_field.choices[1][0] == 'ETH'
