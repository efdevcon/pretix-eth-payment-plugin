from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    NamedTuple,
    Tuple,
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
    def get_transactions(self, to_address: ChecksumAddress) -> Tuple[Transaction, ...]:
        ...


class BlockscoutTransactionProvider(TransactionProviderAPI):
    def get_transactions(self, from_address: ChecksumAddress) -> Tuple[Transaction, ...]:
        response = requests.get(
            f'https://blockscout.com/poa/core/api?module=account&action=txlist&address={from_address}',  # noqa: E501
        )
        # TODO: handle http errors here
        response.raise_for_status()
        response_data = response.json()
        if response_data['status'] != "1":
            raise Exception("TODO: real exception and message")
        return tuple(
            Transaction(
                hash=to_bytes(hexstr=raw_transaction['hash']),
                sender=to_checksum_address(raw_transaction['from']),
                success=(raw_transaction['txreceipt_status'] == 1),
                timestamp=int(raw_transaction['timeStamp']),
                to=to_checksum_address(raw_transaction['to']),
                value=int(raw_transaction['value']),
            ) for raw_transaction in response_data['result']
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
    def get_ERC20_transfers(self, to_address: ChecksumAddress) -> Tuple[Transfer, ...]:
        ...


class BlockscoutTokenProvider(TokenProviderAPI):
    def get_ERC20_transfers(self, from_address: ChecksumAddress) -> Tuple[Transfer, ...]:
        response = requests.get(
            f'https://blockscout.com/poa/dai/api?module=account&action=txlist&address={from_address}',  # noqa: E501
        )
        response.raise_for_status()
        transfer_data = response.json()
        return tuple(
            Transfer(
                hash=to_bytes(hexstr=raw_transfer['hash']),
                sender=to_checksum_address(raw_transfer['from']),
                success=(raw_transfer['txreceipt_status'] == 1),
                timestamp=int(raw_transfer['timeStamp']),
                to=to_checksum_address(raw_transfer['to']),
                value=int(raw_transfer['value']),
            ) for raw_transfer in transfer_data['result']
        )
