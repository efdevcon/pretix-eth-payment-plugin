import os
from typing import (
    Optional,
    Type,
)

from eth_utils import (
    is_boolean,
    is_bytes,
    is_checksum_address,
    is_integer,
)
import pytest

from pretix_eth.providers import (
    BlockscoutMainnetProvider,
    EtherscanGoerliProvider,
    EtherscanMainnetProvider,
    EtherscanRopstenProvider,
    Transaction,
    TransactionProviderAPI,
    Transfer,
)

ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY')
skip_if_no_etherscan_api_key = pytest.mark.skipif(
    ETHERSCAN_API_KEY is None,
    reason='Etherscan api key is not set',
)


class BaseProviderTestSuite:
    provider_class: Optional[Type[TransactionProviderAPI]] = None
    api_key: Optional[str] = None

    wallet_address: Optional[str] = None
    token_address: Optional[str] = None

    start_block: Optional[int] = None
    end_block: Optional[int] = None

    transaction_count: Optional[int] = None
    internal_transaction_count: Optional[int] = None
    transfer_count: Optional[int] = None

    @pytest.fixture(scope='class')
    def provider(self):
        if self.api_key is not None:
            return self.provider_class(api_key=self.api_key)
        else:
            return self.provider_class()

    def test_get_transaction_list(self, provider):
        transactions = provider.get_transaction_list(
            self.wallet_address,
            start_block=self.start_block,
            end_block=self.end_block,
        )

        assert len(transactions) == self.transaction_count

        for txn in transactions:
            assert isinstance(txn, Transaction)
            assert is_bytes(txn.hash) and len(txn.hash)
            assert is_checksum_address(txn.sender)
            assert is_checksum_address(txn.to)
            assert is_integer(txn.value)
            assert is_integer(txn.timestamp)
            assert is_boolean(txn.success)

    def test_get_internal_transaction_list(self, provider):
        transactions = provider.get_internal_transaction_list(
            self.wallet_address,
            start_block=self.start_block,
            end_block=self.end_block,
        )

        assert len(transactions) == self.internal_transaction_count

        for txn in transactions:
            assert isinstance(txn, Transaction)
            assert is_bytes(txn.hash) and len(txn.hash)
            assert is_checksum_address(txn.sender)
            assert is_checksum_address(txn.to)
            assert is_integer(txn.value)
            assert is_integer(txn.timestamp)
            assert is_boolean(txn.success)

    def test_get_transfer_list(self, provider):
        transfers = provider.get_transfer_list(
            self.wallet_address,
            self.token_address,
            start_block=self.start_block,
            end_block=self.end_block,
        )

        assert len(transfers) == self.transfer_count

        for tfr in transfers:
            assert isinstance(tfr, Transfer)
            assert is_bytes(tfr.hash) and len(tfr.hash)
            assert is_checksum_address(tfr.sender)
            assert is_checksum_address(tfr.to)
            assert is_integer(tfr.value)
            assert is_integer(tfr.timestamp)
            assert is_boolean(tfr.success)


MAINNET_START_BLOCK = 8062600
MAINNET_END_BLOCK = 8200000

DEVCON_5_MAINNET_ADDRESS = '0x6a1517622feb74a242e68a26f423ae38e020a0b1'
DAI_MAINNET_ADDRESS = '0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'

ZERO_ADDRESS = '0x' + '00' * 20


class BaseMainnetTestSuite(BaseProviderTestSuite):
    wallet_address = DEVCON_5_MAINNET_ADDRESS
    token_address = DAI_MAINNET_ADDRESS

    start_block = MAINNET_START_BLOCK
    end_block = MAINNET_END_BLOCK

    transaction_count = 112
    internal_transaction_count = 7
    transfer_count = 33


ROPSTEN_START_BLOCK = 6267000
ROPSTEN_END_BLOCK = 6268699

BOND_EUR_ROPSTEN_ADDRESS = '0xf0175b2b2bfd93cceacca66f08d8f54b1e14fc42'


class BaseRopstenTestSuite(BaseProviderTestSuite):
    wallet_address = ZERO_ADDRESS
    token_address = BOND_EUR_ROPSTEN_ADDRESS

    start_block = ROPSTEN_START_BLOCK
    end_block = ROPSTEN_END_BLOCK

    transaction_count = 153
    internal_transaction_count = 1
    transfer_count = 34


GOERLI_START_BLOCK = 961591
GOERLI_END_BLOCK = 1178027

OVERLAY_TOKEN_GOERLI_ADDRESS = '0x70f36e25d9cc6d813587ed106d28cd4195639a9c'


class BaseGoerliTestSuite(BaseProviderTestSuite):
    wallet_address = ZERO_ADDRESS
    token_address = OVERLAY_TOKEN_GOERLI_ADDRESS

    start_block = GOERLI_START_BLOCK
    end_block = GOERLI_END_BLOCK

    transaction_count = 84
    internal_transaction_count = 10
    transfer_count = 7


@skip_if_no_etherscan_api_key
class TestEtherscanMainnetProvider(BaseMainnetTestSuite):
    provider_class = EtherscanMainnetProvider
    api_key = ETHERSCAN_API_KEY


@skip_if_no_etherscan_api_key
class TestEtherscanRopstenProvider(BaseRopstenTestSuite):
    provider_class = EtherscanRopstenProvider
    api_key = ETHERSCAN_API_KEY


@skip_if_no_etherscan_api_key
class TestEtherscanGoerliProvider(BaseGoerliTestSuite):
    provider_class = EtherscanGoerliProvider
    api_key = ETHERSCAN_API_KEY


class TestBlockscoutMainnetProvider(BaseMainnetTestSuite):
    provider_class = BlockscoutMainnetProvider
