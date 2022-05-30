def get_message_to_sign(
        sender_address: str,
        receiver_address: str,
        chain_id: int,
        order_code: str
):
    return f"Please sign this message to prove ownership of your wallet:" \
           f"\nPretix ETH:" \
           f"\nWallet address: {sender_address}" \
           f"\nReceiver address: {receiver_address}" \
           f"\nChain ID: {str(chain_id)}" \
           f"\nOrder code: {order_code}"
