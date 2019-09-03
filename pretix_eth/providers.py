from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    Any,
    Dict,
    NamedTuple,
    Optional,
    Tuple,
    Type,
)
from urllib.parse import (
    urlencode,
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

from .exceptions import (
    TransactionProviderError,
)


JSON = Dict[str, Any]


def get_api_response_data(base_url: str, **kwargs: Any) -> Any:
    """
    Return a generic API result as a decoded json object.
    """
    query = urlencode(kwargs)
    url = f'{base_url}?{query}'

    response = requests.get(url)
    response.raise_for_status()

    return response.json()


class EtherscanMixin:
    """
    Mixin class for etherscan-compatible APIs (e.g. etherscan or blockscout).
    """
    base_url: Optional[str] = None
    error_class: Type[Exception] = Exception
    api_key: Optional[str] = None

    def __init__(self, **kwargs: Any):
        self.api_key = kwargs.pop('api_key', None)

        super().__init__(**kwargs)  # type: ignore

    def raise_for_json_status(self, response_data: JSON) -> None:
        """
        Raises an instance of an appropriate error class if an API response
        indicates that an error occurred.
        """
        status = response_data['status']
        if status != '1':
            message = response_data.get('message', 'No error message given')
            raise self.error_class(
                f'Error status "{status}" in JSON response: {message}'
            )

    def get_api_result(self, **kwargs: Any) -> Any:
        """
        Make a request to an API and return the relevant result data in the
        response.  Raise for error status in JSON.
        """
        if self.base_url is None:
            raise ValueError('Must provide value for `base_url`')

        if self.api_key is not None:
            kwargs.setdefault('apikey', self.api_key)

        response_data = get_api_response_data(self.base_url, **kwargs)
        self.raise_for_json_status(response_data)

        return response_data['result']


class Transaction(NamedTuple):
    """
    Tuple representing a transaction that transfers ether.
    """
    hash: Hash32
    sender: ChecksumAddress
    success: bool
    timestamp: int
    to: ChecksumAddress
    value: int


class Transfer(NamedTuple):
    """
    Tuple representing a transfer of ERC20 tokens.
    """
    hash: Hash32
    sender: ChecksumAddress
    timestamp: int
    success: bool
    to: ChecksumAddress
    token: ChecksumAddress
    value: int


class TransactionProviderAPI(ABC):
    erc20_transfer_id = to_bytes(hexstr='0xa9059cbb')  # transfer(address,uint256)

    @classmethod
    @abstractmethod
    def normalize_transaction_result(cls, result: JSON) -> JSON:
        """
        Return a normalized dictionary representation of a transaction from a
        JSON API result.
        """
        ...

    @classmethod
    @abstractmethod
    def normalize_transfer_result(cls, result: JSON) -> JSON:
        """
        Return a normalized dictionary representation of an ERC20 token
        transfer from a JSON API result.
        """
        ...

    @classmethod
    def transaction_from_result(cls, result: JSON, **kwargs: Any) -> Transaction:
        """
        Return a normalized tuple representation of a transaction from a JSON
        API result.
        """
        res = cls.normalize_transaction_result(result)
        res.update(kwargs)

        return Transaction(
            hash=to_bytes(hexstr=res['hash']),
            sender=to_checksum_address(res['sender']),
            success=res['success'],
            timestamp=int(res['timestamp']),
            to=to_checksum_address(res['to']),
            value=int(res['value']),
        )

    @classmethod
    def transfer_from_result(cls, result: JSON, **kwargs: Any) -> Transfer:
        """
        Return a normalized tuple representation of an ERC20 token transfer
        from a JSON API result.
        """
        res = cls.normalize_transfer_result(result)
        res.update(kwargs)

        return Transfer(
            hash=to_bytes(hexstr=res['hash']),
            sender=to_checksum_address(res['sender']),
            success=res['success'],
            timestamp=int(res['timestamp']),
            to=to_checksum_address(res['to']),
            token=to_checksum_address(res['token']),
            value=int(res['value']),
        )

    @abstractmethod
    def get_transaction_list(self,
                             address: str,
                             start_block: Optional[int] = None,
                             end_block: Optional[int] = None) -> Tuple[Transaction, ...]:
        """
        Return a list of tuples containing information about transactions sent
        to the given address.
        """
        ...

    @abstractmethod
    def get_internal_transaction_list(self,
                                      address: str,
                                      start_block: Optional[int] = None,
                                      end_block: Optional[int] = None) -> Tuple[Transaction, ...]:
        """
        Return a list of tuples containing information about internal
        transactions targeting the given address.
        """
        ...

    @abstractmethod
    def get_transfer_list(self,
                          address: str,
                          token_address: str,
                          start_block: Optional[int] = None,
                          end_block: Optional[int] = None) -> Tuple[Transfer, ...]:
        """
        Return a list of tuples containing information about ERC20 token
        transfers sent to the given address for a given token.
        """
        ...


def normalize_dict(from_dict: Dict[str, Any], key_mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    Return a subset of the values in ``from_dict`` re-keyed according to the
    mapping in ``key_mapping``.  The key mapping dict has the format of
    ``key_mapping[new_key] = old_key``.
    """
    to_dict = {}

    for new_key, old_key in key_mapping.items():
        if old_key in from_dict:
            to_dict[new_key] = from_dict[old_key]

    return to_dict


class BaseEtherscanProvider(EtherscanMixin, TransactionProviderAPI):
    base_url: Optional[str] = None
    error_class = TransactionProviderError

    @classmethod
    def normalize_transaction_result(cls, result: JSON) -> JSON:
        normalized_result = normalize_dict(result, {
            'hash': 'hash',
            'sender': 'from',
            'timestamp': 'timeStamp',
            'to': 'to',
            'value': 'value',
        })

        normalized_result['success'] = result['isError'] == '0'

        return normalized_result

    @classmethod
    def normalize_transfer_result(cls, result: JSON) -> JSON:
        normalized_result = normalize_dict(result, {
            'hash': 'hash',
            'sender': 'from',
            'timestamp': 'timeStamp',
            'to': 'to',
            'value': 'value',
        })

        normalized_result['success'] = True

        return normalized_result

    def get_transaction_list(self,
                             address: str,
                             start_block: Optional[int] = None,
                             end_block: Optional[int] = None) -> Tuple[Transaction, ...]:
        query_params: Dict[str, Any] = {
            'module': 'account',
            'action': 'txlist',
            'address': address,
        }
        if start_block is not None:
            query_params['startblock'] = start_block
        if end_block is not None:
            query_params['endblock'] = end_block

        results = self.get_api_result(**query_params)
        address_lower = address.lower()
        external_txns = [
            self.transaction_from_result(res)
            for res in results
            if res['to'].lower() == address_lower
        ]

        return tuple(external_txns)

    def get_internal_transaction_list(self,
                                      address: str,
                                      start_block: Optional[int] = None,
                                      end_block: Optional[int] = None) -> Tuple[Transaction, ...]:
        query_params: Dict[str, Any] = {
            'module': 'account',
            'action': 'txlistinternal',
            'address': address,
        }
        if start_block is not None:
            query_params['startblock'] = start_block
        if end_block is not None:
            query_params['endblock'] = end_block

        results = self.get_api_result(**query_params)
        address_lower = address.lower()
        internal_txns = [
            self.transaction_from_result(res)
            for res in results
            if res['to'].lower() == address_lower
        ]

        return tuple(internal_txns)

    def get_transfer_list(self,
                          address: str,
                          token_address: str,
                          start_block: Optional[int] = None,
                          end_block: Optional[int] = None) -> Tuple[Transfer, ...]:
        query_params: Dict[str, Any] = {
            'module': 'account',
            'action': 'tokentx',
            'address': address,
            'contractaddress': token_address,
        }
        if start_block is not None:
            query_params['startblock'] = start_block
        if end_block is not None:
            query_params['endblock'] = end_block

        results = self.get_api_result(**query_params)
        address_lower = address.lower()
        transfers = [
            self.transfer_from_result(res, token=token_address)
            for res in results
            if res['to'].lower() == address_lower
        ]

        return tuple(transfers)


class EtherscanMainnetProvider(BaseEtherscanProvider):
    base_url = 'https://api.etherscan.io/api'


class EtherscanRopstenProvider(BaseEtherscanProvider):
    base_url = 'https://api-ropsten.etherscan.io/api'


class EtherscanGoerliProvider(BaseEtherscanProvider):
    base_url = 'https://api-goerli.etherscan.io/api'


class BaseBlockscoutProvider(BaseEtherscanProvider):
    @classmethod
    def normalize_transaction_result(cls, result: JSON) -> JSON:
        res = super().normalize_transaction_result(result)

        # Blockscout returns a 'transactionHash' key in some cases
        res.setdefault('hash', result.get('transactionHash'))

        return res


class BlockscoutMainnetProvider(BaseBlockscoutProvider):
    base_url = 'https://blockscout.com/eth/mainnet/api'
