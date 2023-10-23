import requests
import statistics
import time


def make_erc_681_url(
    to_address, payment_amount, chain_id=1, is_token=False, token_address=None
):
    """Make ERC681 URL based on if transferring ETH or a token like DAI and the chain id"""

    base_url = "ethereum:"
    chain_id_formatted_for_url = "" if chain_id == 1 else f"@{chain_id}"

    if is_token:
        if token_address is None:
            raise ValueError(
                "if is_token is true, then you must pass contract address of the token."
            )

        return (
            base_url
            + token_address
            + chain_id_formatted_for_url
            + f"/transfer?address={to_address}&uint256={payment_amount}"
        )
    # if ETH (not token)
    return (
        base_url + to_address + chain_id_formatted_for_url + f"?value={payment_amount}"
    )


def make_uniswap_url(output_currency, recipient_address, exact_amount):
    """
    Build uniswap url to swap exact_amount of one currency to the required output currency
    and send to a recipient address.
    """
    return f"https://uniswap.exchange/send?exactField=output&exactAmount={exact_amount}&outputCurrency={output_currency}&recipient={recipient_address}"  # noqa: E501


def make_checkout_web3modal_url(
    currency_type, amount_in_ether_or_token, wallet_address, chainId=1
):
    """
    Build a checkout.web3modal.com link that uses web3modal
    to create a tx to pay in ETH/DAI on a chain to a certain address.
    Note: amount_in_ether_or_token is in decimals.
    """
    if currency_type not in {"ETH", "DAI"}:
        raise ValueError("currency_type should be either ETH or DAI")

    return f"https://checkout.web3modal.com/?currency={currency_type}&amount={amount_in_ether_or_token}&to={wallet_address}&chainId={chainId}"  # noqa: E501


api_cache = {}

# List of API endpoints
api_endpoints = [
    "https://api.kraken.com/0/public/Ticker?pair=ETH{currency}",
    "https://api.binance.com/api/v3/ticker/bookTicker?symbol=ETH{currency}",
    "https://api.gemini.com/v1/pubticker/eth{currency}",
    "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=${currency}"
]


def format_api_endpoint(api_endpoint, fiat_currency):
    if fiat_currency == 'USD' and "binance.com" in api_endpoint:
        fiat_currency = 'USDC'

    return api_endpoint.format(currency=fiat_currency)


def fetch_eth_price(api_endpoint, fiat_currency):
    api_endpoint = format_api_endpoint(api_endpoint, fiat_currency)

    # Check if the data is already cached and within the 15-minute window
    if api_endpoint in api_cache:
        cached_data = api_cache[api_endpoint]
        current_time = time.time()
        if current_time - cached_data["timestamp"] <= 900:
            return cached_data["price"]

    try:
        response = requests.get(api_endpoint)
        data = response.json()

        # Extract ETH price from each API response based on the endpoint
        if "kraken.com" in api_endpoint:
            eth_price = float(data["result"]["XETHZ" + fiat_currency.upper()]["c"][0])
        elif "binance.com" in api_endpoint:
            eth_price = float(data["bidPrice"])
        elif "gemini.com" in api_endpoint:
            eth_price = float(data["last"])
        elif "coingecko.com" in api_endpoint:
            eth_price = float(data['ethereum'][fiat_currency.lower()])
        else:
            eth_price = None

        if eth_price is not None:
            # Cache the data with the ETH price and timestamp
            api_cache[api_endpoint] = {"price": eth_price, "timestamp": time.time()}

        return eth_price
    except Exception as e:
        print(f"Error fetching data from {api_endpoint}: {e}")
        return None


def get_eth_price_from_external_apis(fiat_currency):
    # Fetch prices from all API endpoints
    eth_prices = [fetch_eth_price(endpoint, fiat_currency) for endpoint in api_endpoints]

    # Filter out None values (indicating errors)
    eth_prices = [price for price in eth_prices if price is not None]

    # Calculate the average price while discarding values that deviate too much
    if eth_prices:
        return statistics.median(eth_prices)
    else:
        print("No valid API results to calculate an average.")
        return None
