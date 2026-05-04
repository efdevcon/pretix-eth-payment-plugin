# tests/core/test_x402_gas.py
from unittest import mock
import pytest
from pretix_eth.x402.gas import GAS_CAPS_GWEI, assert_gas_conditions, GasConditionError


def test_gas_caps_defined_for_all_chains():
    for cid in [1, 10, 137, 8453, 42161]:
        assert cid in GAS_CAPS_GWEI
        assert GAS_CAPS_GWEI[cid] > 0


def test_gas_too_high_raises():
    w3 = mock.MagicMock()
    w3.eth.gas_price = 5 * 10**9  # 5 gwei
    with pytest.raises(GasConditionError, match='gas price'):
        # Base cap is 0.13 gwei — 5 gwei exceeds it
        assert_gas_conditions(w3=w3, chain_id=8453)


def test_gas_ok_passes():
    w3 = mock.MagicMock()
    w3.eth.gas_price = 10**8  # 0.1 gwei (under 0.13 cap for Base)
    # Should not raise; balance is intentionally not checked here anymore.
    assert_gas_conditions(w3=w3, chain_id=8453)


def test_unknown_chain_raises():
    w3 = mock.MagicMock()
    w3.eth.gas_price = 10**8
    with pytest.raises(GasConditionError, match='No gas cap'):
        assert_gas_conditions(w3=w3, chain_id=999999)
