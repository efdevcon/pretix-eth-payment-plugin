from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    Any,
    Dict,
    NamedTuple,
    Type,
)

import requests

from eth_abi import (
    decode_single,
)
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

from .exceptions import (
    TokenProviderError,
    TransactionProviderError,
)


JSON = Dict[str, Any]


class BlockscoutMixin:
    error_class: Type[Exception] = Exception

    def raise_for_json_status(self, response_data: JSON) -> None:
        """
        Raises an instance of an appropriate error class if a blockscout API
        response indicates that an error occurred.
        """
        status = response_data['status']
        if status != '1':
            message = response_data.get('message', 'No error message given')
            raise self.error_class(
                f'Token API returned error status {status}: {message}'
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


class BlockscoutTransactionProvider(BlockscoutMixin, TransactionProviderAPI):
    error_class = TransactionProviderError

    def get_transaction(self, txn_hash: str) -> Transaction:
        response = requests.get(
            f'https://blockscout.com/eth/mainnet/api?module=transaction&action=gettxinfo&txhash={txn_hash}',  # noqa: E501
        )

        response.raise_for_status()
        response_data = response.json()
        self.raise_for_json_status(response_data)

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


class BlockscoutTokenProvider(BlockscoutMixin, TokenProviderAPI):
    error_class = TokenProviderError
    token_address = '0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'  # Mainnet DAI address
    transfer_method_id = to_bytes(hexstr='0xa9059cbb')  # Method id for ERC20 "transfer(address,uint256)"

    def get_ERC20_transfer(self, txn_hash: str) -> Transfer:
        response = requests.get(
            f'http://blockscout.com/eth/mainnet/api?module=transaction&action=gettxinfo&txhash={txn_hash}',  # noqa: E501
        )

        response.raise_for_status()
        response_data = response.json()
        self.raise_for_json_status(response_data)

        txn_data = response_data['result']

        # Transaction "to" address is the token contract address
        txn_token_address = txn_data['to']
        if txn_token_address != self.token_address:
            raise self.error_class(
                'Unrecognized token address: '
                f'{txn_token_address} (actual) != {self.token_address} (expected)'
            )

        # Input data for transaction contains target address and amount for DAI
        # transfer
        input_data = to_bytes(hexstr=txn_data['input'])
        method_id = input_data[:4]
        if method_id != self.transfer_method_id:
            raise self.error_class(
                'Unrecognized method id: '
                f'{method_id} (actual) != {self.transfer_method_id} (expected)'
            )

        method_data = input_data[4:]
        decoded_method_data = decode_single('(address,uint256)', method_data)

        to = decoded_method_data[0]
        value = decoded_method_data[1]

        return Transfer(
            hash=to_bytes(hexstr=txn_data['hash']),
            sender=to_checksum_address(txn_data['from']),
            success=txn_data['success'],
            timestamp=int(txn_data['timeStamp']),
            to=to_checksum_address(to),
            value=value,
        )
