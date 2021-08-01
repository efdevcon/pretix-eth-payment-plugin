def make_erc_681_url(
    to_address, payment_amount, chain_id=1, is_token=False, token_address=None
):
    """Make ERC681 URL based on if transferring ETH or a token like DAI and the chain id"""
    if is_token:
        if token_address == None:
            raise ValueError(
                "if is_token is true, then you must pass contract address of the token."
            )

        return f"ethereum:{token_address}@{chain_id}/transfer?address={to_address}&uint256={payment_amount}"  # noqa: E501
    # if ETH (not token)
    return f"ethereum:{to_address}@{chain_id}?value={payment_amount}"


def make_uniswap_url(
    output_currency, recipient_address, exact_amount, input_currency=None
):
    """
    Build uniswap url to swap exact_amount of one currency to another and send to a address.
    Input currency may not be fixed but output_currency must be provided.
    """
    url = f"https://uniswap.exchange/send?exactField=output&exactAmount={exact_amount}&outputCurrency={output_currency}&recipient={recipient_address}"  # noqa: E501

    if input_currency == None:
        return url

    # else - swap between a fixed currency to another:
    return url + f"&inputCurrency={input_currency}"


def make_checkout_web3modal_url(
    currency_type, amount_in_ether_or_token, wallet_address, chainId=1
):
    """
    Build a checkout.web3modal.com link that uses web3modal to create a tx to pay in ETH/DAI on a chain to a certain address.
    Note: amount_in_ether_or_token is in decimals.
    """
    if currency_type not in {"ETH", "DAI"}:
        raise ValueError("currency_type should be either ETH or DAI")

    return f"https://checkout.web3modal.com/?currency={currency_type}&amount={amount_in_ether_or_token}&to={wallet_address}&chainId={chainId}"  # noqa: E501


# Useful to create a separate token payment isntruction function since 
# in the future, we will support multiple token
def token_in_evm_payment_instructions(
    wallet_address, payment_amount, token_contract_address, chain_id=1, use_uniswap=True, amount_in_ether_or_token=None
):
    """
    :param wallet_address: address to pay to
    :param payment_amount: amount to pay (in wei)
    :param token_contract_address: smart contract address of the token for the chain
    :param chain_id: of the chain to transact on. by default 1 (ETH L1)
    :param use_uniswap: does the chain have uniswap? boolean.
    :param amount_in_ether_or_token: amount to pay (from_wei(payment_amount)). Used only if uniswap is used.
    :returns erc_681_url, uniswap_url (can be None)
    """

    if use_uniswap and amount_in_ether_or_token==None:
        raise ValueError("Must supply amount_in_ether_or_token (from_wei(payment_amount)) if using uniswap")
    
    erc_681_url = make_erc_681_url(
        wallet_address,
        payment_amount,
        chain_id,
        is_token=True,
        token_address=token_contract_address,
    )
    uniswap_url = None
    if use_uniswap:
        uniswap_url = make_uniswap_url(token_contract_address, wallet_address, amount_in_ether_or_token)

    return erc_681_url, uniswap_url


def evm_like_payment_instructions(
    wallet_address, payment_amount, currency_type, chain_token_address, chain_id=1, amount_in_ether_or_token=None, use_uniswap=True
):
    """
    Instructions for paying ETH or a token (e.g. DAI) on an ethereum chain. 
    Instructions to pay manually, via a web3 modal, ERC 681 (QR Code) or uniswap url.

    :param wallet_address: address to pay to
    :param payment_amount: amount to pay (in wei)
    :param currency_type: ETH or token_name e.g. DAI
    :param token_contract_address: smart contract address of the token for the chain
    :param chain_id: of the chain to transact on. by default 1 (ETH L1)
    :param amount_in_ether_or_token: amount to pay (from_wei(payment_amount)). Used only if uniswap is used.
    :param use_uniswap: does the chain have uniswap? boolean.
    :returns dictionary: {
        "erc_681_url": erc_681_url,
        "uniswap_url": uniswap_url,
        "web3modal_url": web3modal_url,
        "amount_manual": amount_manual,
        "wallet_address": wallet_address,
    }
    """
    uniswap_url = None

    if currency_type == "ETH":
        erc_681_url = make_erc_681_url(wallet_address, payment_amount, chain_id)
        
        if use_uniswap:
            uniswap_url = make_uniswap_url(
                "ETH", wallet_address, amount_in_ether_or_token, chain_token_address
            )

    elif currency_type == "DAI":
        erc_681_url, uniswap_url = token_in_evm_payment_instructions(
            wallet_address, payment_amount, chain_token_address, chain_id, use_uniswap, amount_in_ether_or_token
        )

    else:
        raise ImproperlyConfigured(f"Unrecognized currency: {currency_type}")

    amount_manual = f"{amount_in_ether_or_token} {currency_type}"
    web3modal_url = make_checkout_web3modal_url(
        currency_type, amount_in_ether_or_token, wallet_address, chain_id
    )

    return {
        "erc_681_url": erc_681_url,
        "uniswap_url": uniswap_url,
        "web3modal_url": web3modal_url,
        "amount_manual": amount_manual,
        "wallet_address": wallet_address,
    }
