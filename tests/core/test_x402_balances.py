from unittest import mock
import pytest
from pretix_eth.x402.balances import fetch_balances_for_wallet


def test_fetch_balances_uses_correct_rpc(monkeypatch):
    def fake_get_rpc(chain_id, settings_key):
        return f'https://fake-rpc-{chain_id}'
    monkeypatch.setattr('pretix_eth.x402.balances.get_rpc_url', fake_get_rpc)

    # Mock Web3 client
    fake_web3 = mock.MagicMock()
    fake_web3.eth.get_balance.return_value = 5 * 10**17  # 0.5 ETH
    fake_contract = mock.MagicMock()
    fake_contract.functions.balanceOf.return_value.call.return_value = 50 * 10**6  # 50 USDC
    fake_web3.eth.contract.return_value = fake_contract
    monkeypatch.setattr('pretix_eth.x402.balances.Web3', mock.MagicMock(return_value=fake_web3))

    result = fetch_balances_for_wallet(
        wallet='0x' + '1' * 40, chain_ids=[8453], alchemy_key=None,
    )
    assert len(result) > 0
    eth_entry = next((e for e in result if e['symbol'] == 'ETH'), None)
    assert eth_entry is not None
    assert eth_entry['balance'] == str(5 * 10**17)


def test_fetch_balances_prefers_zapper_when_key_set(monkeypatch):
    """Zapper fast path is used when key is set; RPC is not called."""
    def boom(*args, **kwargs):
        raise AssertionError('RPC path should not run when Zapper succeeds')
    monkeypatch.setattr('pretix_eth.x402.balances._fetch_balances_via_rpc', boom)

    fake_zapper_result = [
        {'chain_id': 8453, 'symbol': 'ETH', 'balance': '123', 'decimals': 18, 'token_address': None},
    ]
    monkeypatch.setattr(
        'pretix_eth.x402.balances.fetch_balances_via_zapper',
        lambda **kw: fake_zapper_result,
    )

    result = fetch_balances_for_wallet(
        wallet='0x' + '1' * 40, chain_ids=[8453], alchemy_key=None,
        zapper_api_key='fake-key',
    )
    assert result == fake_zapper_result


def test_fetch_balances_falls_back_to_rpc_on_zapper_failure(monkeypatch):
    """Zapper returning None triggers the RPC fallback."""
    monkeypatch.setattr(
        'pretix_eth.x402.balances.fetch_balances_via_zapper',
        lambda **kw: None,
    )
    rpc_result = [
        {'chain_id': 8453, 'symbol': 'ETH', 'balance': '999', 'decimals': 18, 'token_address': None},
    ]
    monkeypatch.setattr(
        'pretix_eth.x402.balances._fetch_balances_via_rpc',
        lambda **kw: rpc_result,
    )

    result = fetch_balances_for_wallet(
        wallet='0x' + '1' * 40, chain_ids=[8453], alchemy_key=None,
        zapper_api_key='fake-key',
    )
    assert result == rpc_result


def test_fetch_balances_skips_zapper_when_no_key(monkeypatch):
    """No key — Zapper not called at all; goes straight to RPC."""
    def boom(**kw):
        raise AssertionError('Zapper should not run without an api key')
    monkeypatch.setattr('pretix_eth.x402.balances.fetch_balances_via_zapper', boom)
    rpc_result = []
    monkeypatch.setattr(
        'pretix_eth.x402.balances._fetch_balances_via_rpc',
        lambda **kw: rpc_result,
    )

    result = fetch_balances_for_wallet(
        wallet='0x' + '1' * 40, chain_ids=[8453], alchemy_key=None,
    )
    assert result is rpc_result
