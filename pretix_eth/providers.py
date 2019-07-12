from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    NamedTuple,
)

import requests

from eth_typing import (
    Hash32,
)
from eth_utils import (
    to_bytes,
    to_checksum_address,
)
from eth_utils.typing.misc import (
    ChecksumAddress,
)


class Transaction(NamedTuple):
    hash: Hash32
    sender: ChecksumAddress
    success: bool
    timestamp: int
    to: ChecksumAddress
    value: int


class TransactionProviderAPI(ABC):
    @abstractmethod
    def get_transaction(self, txn_hash: str) -> Transaction:
        ...


class BlockscoutTransactionProvider(TransactionProviderAPI):
    def get_transaction(self, txn_hash: str) -> Transaction:
        response = requests.get(
            f'https://blockscout.com/eth/mainnet/api?module=transaction&action=gettxinfo&txhash={txn_hash}',  # noqa: E501
        )

        response.raise_for_status()
        response_data = response.json()

        if response_data['status'] != "1":
            raise Exception("TODO: real exception and message")

        raw_transaction = response_data['result']

        return Transaction(
            hash=to_bytes(hexstr=raw_transaction['hash']),
            sender=to_checksum_address(raw_transaction['from']),
            success=raw_transaction['success'],
            timestamp=int(raw_transaction['timeStamp']),
            to=to_checksum_address(raw_transaction['to']),
            value=int(raw_transaction['value']),
        )


class Transfer(NamedTuple):
    hash: Hash32
    sender: ChecksumAddress
    timestamp: int
    success: bool
    to: ChecksumAddress
    value: int


class TokenProviderAPI(ABC):
    @abstractmethod
    def get_ERC20_transfer(self, txn_hash: str) -> Transfer:
        ...


class BlockscoutTokenProvider(TokenProviderAPI):
    def get_ERC20_transfer(self, txn_hash: str) -> Transfer:
        response = requests.get(
            f'http://blockscout.com/poa/dai/api?module=transaction&action=gettxinfo&txhash={txn_hash}',  # noqa: E501
        )

        response.raise_for_status()
        transfer_data = response.json()

        raw_transfer = transfer_data['result']

        return Transfer(
            hash=to_bytes(hexstr=raw_transfer['hash']),
            sender=to_checksum_address(raw_transfer['from']),
            success=raw_transfer['success'],
            timestamp=int(raw_transfer['timeStamp']),
            to=to_checksum_address(raw_transfer['to']),
            value=int(raw_transfer['value']),
        )
