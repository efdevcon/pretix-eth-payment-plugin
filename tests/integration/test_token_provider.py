from pretix_eth.providers import BlockscoutTokenProvider

from eth_utils import (
    is_boolean,
    is_checksum_address,
    is_bytes,
    is_integer,
)


META_CARTEL_ADDRESS = '0xa1c3Eb21cD44F0433c6be936AD84D20b70B564D3'


def test_blockscout_transaction_provider():
    provider = BlockscoutTokenProvider()
    transfers = provider.get_ERC20_transfers(META_CARTEL_ADDRESS)
    assert len(transfers) > 0
    assert all(
        is_bytes(tx.hash) and len(tx.hash) == 32
        for tx in transfers
    )
    assert all(
        is_checksum_address(tx.sender)
        for tx in transfers
    )
    assert all(
        is_checksum_address(tx.to)
        for tx in transfers
    )
    assert all(tuple(
        is_integer(tx.value)
        for tx in transfers
    ))
    assert all(
        is_integer(tx.timestamp)
        for tx in transfers
    )
    assert all(
        is_boolean(tx.success)
        for tx in transfers
    )
