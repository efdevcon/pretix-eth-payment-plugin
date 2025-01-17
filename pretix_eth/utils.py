import json
import logging

# from eth_account._utils.structured_data.validation import validate_structured_data


logger = logging.getLogger(__name__)


def get_rpc_url_for_network(payment_provider, network_id):
    rpc_urls = json.loads(payment_provider.settings.NETWORK_RPC_URL)

    expected_network_rpc_url_key = f"{network_id}_RPC_URL"

    if expected_network_rpc_url_key in rpc_urls:
        return rpc_urls[expected_network_rpc_url_key]
    else:
        logger.warning(f"No RPC URL configured for {network_id}. Skipping...")
        return None
