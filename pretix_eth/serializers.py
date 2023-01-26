from rest_framework.serializers import Serializer, ModelSerializer
from rest_framework import fields

from pretix.base.models import Order

from pretix_eth.models import SignedMessage
from pretix_eth.network.tokens import IToken, all_token_and_network_ids_to_tokens
from pretix_eth.utils import get_message_to_sign


class TransactionDetailsSerializer(Serializer):
    chain_id = fields.IntegerField()
    currency = fields.CharField()
    # contract address for non-native ERC20 currencies like DAI
    erc20_contract_address = fields.CharField(allow_null=True)
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

        another_signature_submitted = SignedMessage.objects.filter(
            order_payment__order=instance.order,
            invalid=False
        ).exists()

        # don't let the user pay for multiple order payments wwithin one order
        return {
            "chain_id": token.CHAIN_ID,
            "network_identifier": token.NETWORK_IDENTIFIER,
            "currency": token.TOKEN_SYMBOL,
            "erc20_contract_address": token.ADDRESS,
            "recipient_address": recipient_address,
            "amount": str(instance.info_data.get('amount')),
            "message": get_message_to_sign(
                sender_address=self.context.get('request').query_params.get(
                    'sender_address'),
                receiver_address=recipient_address,
                chain_id=token.CHAIN_ID,
                order_code=instance.order.code
            ),
            "is_signature_submitted": another_signature_submitted,
            "has_other_unpaid_orders": None,
        }


class PaymentStatusSerializer(ModelSerializer):

    class Meta:
        model = Order
        fields = ('status',)
