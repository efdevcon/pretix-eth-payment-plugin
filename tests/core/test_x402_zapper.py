"""Unit tests for the Zapper GraphQL fast-path balance fetcher."""
from unittest import mock

import pytest

from pretix_eth.x402 import zapper


def _make_response(payload: dict):
    """Build a fake context-manager response object the way urlopen returns one."""
    resp = mock.MagicMock()
    import json as _json
    resp.read.return_value = _json.dumps(payload).encode('utf-8')
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_zapper_returns_none_without_api_key():
    assert zapper.fetch_balances_via_zapper(
        wallet='0x' + '1' * 40, chain_ids=[8453], api_key=None,
    ) is None


def test_zapper_parses_balances_per_chain(monkeypatch):
    # Returned shape: USDC on Base + native ETH on Base, plus an unsupported token we should drop.
    payload = {
        'data': {
            'portfolio': {
                'tokenBalances': [
                    {
                        'address': '0x' + '1' * 40,
                        'network': 'BASE_MAINNET',
                        'token': {
                            'balanceRaw': '500000',
                            'baseToken': {
                                'address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
                                'symbol': 'USDC',
                            },
                        },
                    },
                    {
                        'address': '0x' + '1' * 40,
                        'network': 'BASE_MAINNET',
                        'token': {
                            'balanceRaw': '700000000000000000',
                            'baseToken': {
                                'address': '0x0000000000000000000000000000000000000000',
                                'symbol': 'ETH',
                            },
                        },
                    },
                    {
                        'address': '0x' + '1' * 40,
                        'network': 'BASE_MAINNET',
                        'token': {
                            'balanceRaw': '1',
                            'baseToken': {
                                'address': '0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                                'symbol': 'JUNK',
                            },
                        },
                    },
                ],
            },
        },
    }
    monkeypatch.setattr(zapper.urlrequest, 'urlopen',
                        lambda req, timeout=None: _make_response(payload))

    result = zapper.fetch_balances_via_zapper(
        wallet='0x' + '1' * 40, chain_ids=[8453], api_key='fake',
    )

    assert result is not None
    by_sym = {(e['chain_id'], e['symbol']): e for e in result}
    assert by_sym[(8453, 'USDC')]['balance'] == '500000'
    assert by_sym[(8453, 'ETH')]['balance'] == '700000000000000000'
    # Unsupported token must be dropped — only USDC + ETH on Base.
    assert all(e['symbol'] in ('USDC', 'ETH') for e in result if e['chain_id'] == 8453)


def test_zapper_backfills_zero_for_missing_chains(monkeypatch):
    """When Zapper returns no entry for a chain, we still emit a zero row."""
    payload = {'data': {'portfolio': {'tokenBalances': []}}}
    monkeypatch.setattr(zapper.urlrequest, 'urlopen',
                        lambda req, timeout=None: _make_response(payload))

    result = zapper.fetch_balances_via_zapper(
        wallet='0x' + '1' * 40, chain_ids=[8453], api_key='fake',
    )

    assert result is not None
    eth = next((e for e in result if e['chain_id'] == 8453 and e['symbol'] == 'ETH'), None)
    usdc = next((e for e in result if e['chain_id'] == 8453 and e['symbol'] == 'USDC'), None)
    assert eth is not None and eth['balance'] == '0'
    assert usdc is not None and usdc['balance'] == '0'


def test_zapper_returns_none_on_graphql_errors(monkeypatch):
    payload = {'errors': [{'message': 'schema mismatch'}]}
    monkeypatch.setattr(zapper.urlrequest, 'urlopen',
                        lambda req, timeout=None: _make_response(payload))

    assert zapper.fetch_balances_via_zapper(
        wallet='0x' + '1' * 40, chain_ids=[8453], api_key='fake',
    ) is None


def test_zapper_returns_none_on_http_error(monkeypatch):
    def boom(req, timeout=None):
        from urllib.error import HTTPError
        raise HTTPError(req.full_url, 400, 'Bad Request', {}, None)
    monkeypatch.setattr(zapper.urlrequest, 'urlopen', boom)

    assert zapper.fetch_balances_via_zapper(
        wallet='0x' + '1' * 40, chain_ids=[8453], api_key='fake',
    ) is None


def test_zapper_returns_none_on_timeout(monkeypatch):
    def boom(req, timeout=None):
        raise TimeoutError('slow')
    monkeypatch.setattr(zapper.urlrequest, 'urlopen', boom)

    assert zapper.fetch_balances_via_zapper(
        wallet='0x' + '1' * 40, chain_ids=[8453], api_key='fake',
    ) is None
