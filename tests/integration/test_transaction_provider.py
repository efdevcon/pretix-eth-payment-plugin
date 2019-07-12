from pretix_eth.providers import BlockscoutTransactionProvider

from eth_utils import (
    is_boolean,
    is_checksum_address,
    is_bytes,
    is_integer,
)


MAINNET_ETH_TXN_HASH = '0x9d077f68e2cb1f5da6e901081bf51c2501942388d184516d577b2065c61b2975'


def test_blockscout_transaction_provider():
    provider = BlockscoutTransactionProvider()

    tx = provider.get_transaction(MAINNET_ETH_TXN_HASH)

    assert is_bytes(tx.hash) and len(tx.hash)
    assert is_checksum_address(tx.sender)
    assert is_checksum_address(tx.to)
    assert is_integer(tx.value)
    assert is_integer(tx.timestamp)
    assert is_boolean(tx.success)
