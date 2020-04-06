from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore

import pytest


TEST_ETH_RATE = '0.004'
TEST_DAI_RATE = '1.0'
CURRENCY_RATE_SETTINGS = (
    'ETH_RATE',
    'DAI_RATE',
)


@pytest.mark.django_db
def test_provider_properties(provider):
    assert provider.identifier == 'ethereum'
    assert provider.verbose_name == 'ETH or DAI'
    assert provider.public_name == 'ETH or DAI'


@pytest.mark.django_db
def test_provider_settings_form_fields(provider):
    form_fields = provider.settings_form_fields

    assert 'ETH_RATE' in form_fields
    assert 'DAI_RATE' in form_fields


@pytest.mark.django_db
def test_provider_is_allowed(event, provider):
    for setting in CURRENCY_RATE_SETTINGS:
        assert provider.settings.get(setting) is None

    factory = RequestFactory()

    session = SessionStore()
    session.create()

    request = factory.get('/checkout')
    request.event = event
    request.session = session

    assert not provider.is_allowed(request)

    for setting in CURRENCY_RATE_SETTINGS:
        provider.settings.set(setting, '1.0')
        assert provider.is_allowed(request)
        provider.settings.set(setting, '')
        assert not provider.is_allowed(request)

    for setting in CURRENCY_RATE_SETTINGS:
        provider.settings.set(setting, '1.0')

    assert provider.is_allowed(request)


@pytest.mark.django_db
def test_provider_payment_form_fields_only_ETH(provider):
    provider.settings.set('ETH_RATE', TEST_ETH_RATE)

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields['currency_type']

    assert len(currency_type_field.choices) == 1

    choice = currency_type_field.choices[0]

    assert choice[0] == 'ETH'


@pytest.mark.django_db
def test_provider_payment_form_fields_only_DAI(provider):
    provider.settings.set('DAI_RATE', TEST_DAI_RATE)

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields['currency_type']

    assert len(currency_type_field.choices) == 1

    choice = currency_type_field.choices[0]

    assert choice[0] == 'DAI'


@pytest.mark.django_db
def test_provider_payment_form_fields_both_ETH_and_DAI(provider):
    provider.settings.set('DAI_RATE', TEST_DAI_RATE)
    provider.settings.set('ETH_RATE', TEST_ETH_RATE)

    payment_form_fields = provider.payment_form_fields
    currency_type_field = payment_form_fields['currency_type']

    assert len(currency_type_field.choices) == 2

    dai_choice = currency_type_field.choices[0]
    eth_choice = currency_type_field.choices[1]

    assert dai_choice[0] == 'DAI'
    assert eth_choice[0] == 'ETH'
