from pretix_eth.providers import BlockscoutTokenProvider

from eth_utils import (
    is_boolean,
    is_checksum_address,
    is_bytes,
    is_integer,
)


MAINNET_DAI_TXN_HASH = '0x4122bca6b9304170d02178c616185594b05ca1562e8893afa434f4df8d600dfa'


def test_blockscout_transaction_provider():
    provider = BlockscoutTokenProvider()

    tx = provider.get_ERC20_transfer(MAINNET_DAI_TXN_HASH)

    assert is_bytes(tx.hash) and len(tx.hash)
    assert is_checksum_address(tx.sender)
    assert is_checksum_address(tx.to)
    assert is_integer(tx.value)
    assert is_integer(tx.timestamp)
    assert is_boolean(tx.success)
