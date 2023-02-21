import json
import logging

from eth_account._utils.structured_data.validation import validate_structured_data


logger = logging.getLogger(__name__)


def get_message_to_sign(
        sender_address: str, receiver_address: str, chain_id: int,
        order_code: str
):
    message_structured = {
        "domain": {
            "chainId": chain_id,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
            "name": "Pretix-ETH-DAI-plugin",
            "version": "1",
        },
        "message": {
            "sender_address": sender_address,
            "receiver_address": receiver_address,
            "chain_id": chain_id,
            "order_code": order_code,
        },
        "primaryType": "Message",
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Message": [
                {"name": "sender_address", "type": "address"},
                {"name": "receiver_address", "type": "address"},
                {"name": "chain_id", "type": "uint256"},
                {"name": "order_code", "type": "string"},
            ],
        },
    }

    validate_structured_data(message_structured)
    return message_structured


def get_rpc_url_for_network(payment_provider, network_id):
    rpc_urls = json.loads(payment_provider.settings.NETWORK_RPC_URL)

    expected_network_rpc_url_key = f"{network_id}_RPC_URL"

    print('hello', network_id)

    if expected_network_rpc_url_key in rpc_urls:
        return rpc_urls[expected_network_rpc_url_key]
    else:
        logger.warning(f"No RPC URL configured for {network_id}. Skipping...")
        return None
