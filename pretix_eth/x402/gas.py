# pretix_eth/x402/gas.py
"""Gas price caps (ported from relayer.ts lines 80-86)."""


class GasConditionError(Exception):
    pass


# Maximum gas price we're willing to pay (relayer subsidy), in gwei.
# Sourced from devcon src/services/relayer.ts GAS_PRICE_CAPS.
GAS_CAPS_GWEI = {
    1: 50.0,       # Ethereum mainnet
    10: 0.05,      # Optimism
    137: 500.0,    # Polygon
    8453: 0.13,    # Base
    42161: 0.3,    # Arbitrum
}

# TODO: relayer balance monitoring is not enforced at tx time anymore; a drained
# wallet surfaces only when a customer tries to pay. Add an admin-UI dashboard
# / alerting path (e.g. periodic probe + warning banner) so operators learn
# about low balances out-of-band.


def assert_gas_conditions(*, w3, chain_id: int) -> None:
    """Raise GasConditionError if the current network gas price is above our cap.
    We no longer check relayer balance — if the wallet is empty, the RPC will
    reject the tx with InsufficientFunds and the view translates that to a
    non-retryable 502 for the client."""
    cap = GAS_CAPS_GWEI.get(chain_id)
    if cap is None:
        raise GasConditionError(f'No gas cap configured for chain {chain_id}')
    current_gwei = w3.eth.gas_price / 10**9
    if current_gwei > cap:
        raise GasConditionError(
            f'gas price {current_gwei:.4f} gwei exceeds cap {cap} gwei on chain {chain_id}',
        )
