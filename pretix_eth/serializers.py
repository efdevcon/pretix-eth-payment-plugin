from rest_framework.serializers import Serializer
from rest_framework import fields

from pretix_eth.network.tokens import IToken, all_token_and_network_ids_to_tokens
from pretix_eth.utils import get_message_to_sign

# todo model for signatures?
# todo address get param


class TransactionDetailsSerializer(Serializer):
    chain_id = fields.IntegerField()
    currency = fields.CharField()
    erc20_contract_address = fields.CharField(allow_null=True)  # contract address for non-native currencies like DAI
    recipient_address = fields.CharField()
    amount = fields.CharField()
    message = fields.CharField()
    is_signature_submitted = fields.BooleanField()
    has_other_unpaid_orders = fields.BooleanField()

    _context = None

    def to_representation(self, instance):
        token: IToken = all_token_and_network_ids_to_tokens[
            instance.info_data.get('currency_type')
        ]

        recipient_address = instance.payment_provider.get_receiving_address()

        return {
            "chain_id": token.CHAIN_ID,
            "currency": token.TOKEN_SYMBOL,
            "erc20_contract_address":  None,  # todo
            "recipient_address": recipient_address,
            "amount": str(instance.info_data.get('amount')),
            "message": get_message_to_sign(
                sender_address=self.context.get('request').query_params.get('sender_address'),
                receiver_address=recipient_address,
                chain_id=token.CHAIN_ID,
                order_code=instance.order.code
            ),
            "is_signature_submitted": instance.signed_messages.exists(),
            "has_other_unpaid_orders": None,  # todo

        }
