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
