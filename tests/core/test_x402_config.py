# tests/core/test_x402_config.py
import os
from unittest import mock
from pretix_eth.x402.config import resolve_relayer_pk


def test_env_wins_over_setting():
    with mock.patch.dict(os.environ, {'WC_RELAYER_PRIVATE_KEY': '0xenv'}):
        assert resolve_relayer_pk('0xsetting') == '0xenv'


def test_setting_used_when_no_env():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop('WC_RELAYER_PRIVATE_KEY', None)
        assert resolve_relayer_pk('0xsetting') == '0xsetting'


def test_both_missing_returns_none():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop('WC_RELAYER_PRIVATE_KEY', None)
        assert resolve_relayer_pk(None) is None
        assert resolve_relayer_pk('') is None


