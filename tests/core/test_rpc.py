import os
import pytest
from unittest import mock
from pretix_eth.rpc import get_rpc_url


def test_public_fallback_when_no_key():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop('WC_ALCHEMY_API_KEY', None)
        url = get_rpc_url(8453, settings_key=None)
        assert 'publicnode.com' in url


def test_env_key_takes_precedence():
    with mock.patch.dict(os.environ, {'WC_ALCHEMY_API_KEY': 'envkey'}):
        url = get_rpc_url(8453, settings_key='settingskey')
        assert 'alchemy.com' in url
        assert 'envkey' in url
        assert 'settingskey' not in url


def test_settings_key_when_no_env():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop('WC_ALCHEMY_API_KEY', None)
        url = get_rpc_url(10, settings_key='settingskey')
        assert 'opt-mainnet.g.alchemy.com' in url
        assert 'settingskey' in url


def test_unknown_chain_raises():
    with pytest.raises(ValueError):
        get_rpc_url(999, settings_key=None)
