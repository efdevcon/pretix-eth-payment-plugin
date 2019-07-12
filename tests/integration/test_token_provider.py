from pretix_eth.providers import BlockscoutTokenProvider

from eth_utils import (
    is_boolean,
    is_checksum_address,
    is_bytes,
    is_integer,
)


POA_DAI_TXN_HASH = '0x67c4d34ff58351d196bdd74160b3a93d4e3298c5dd8423aa954f268f3f54d610'


def test_blockscout_transaction_provider():
    provider = BlockscoutTokenProvider()

    tx = provider.get_ERC20_transfer(POA_DAI_TXN_HASH)

    assert is_bytes(tx.hash) and len(tx.hash)
    assert is_checksum_address(tx.sender)
    assert is_checksum_address(tx.to)
    assert is_integer(tx.value)
    assert is_integer(tx.timestamp)
    assert is_boolean(tx.success)
