import json

from web3 import Web3
from eth_account.messages import encode_structured_data, encode_defunct, defunct_hash_message
from web3.providers.auto import load_provider_from_uri

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404

from pretix.base.models import Order, OrderPayment

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework import permissions, mixins

from pretix_eth import serializers
from pretix_eth.models import SignedMessage
from pretix_eth.utils import get_rpc_url_for_network
from pretix_eth.network import tokens

magic_value = '0x1626ba7e'
eip1271abi = [{"inputs": [{"name": "_hash", "type": "bytes32"}, {"name": "_signature", "type": "bytes"}], "name": "isValidSignature", "outputs": [
    {"name": "magicValue", "type": "bytes4"}], "stateMutability": "view", "type": "function"}]


def is_smart_contract(address, w3):
    bytecode = w3.eth.getCode(address)
    return bytecode != b''


def reconstruct_message_hash(sender=str, receiver=str, order=str, chain_id=int):
    return defunct_hash_message(text=sender + receiver + order + str(chain_id))


def validate_eip1271_signature(sender, signature, hash, w3):
    signatureAsBytes = Web3.to_bytes(hexstr=signature)

    contract = w3.eth.contract(address=sender, abi=eip1271abi)
    response = contract.functions.isValidSignature(hash, signatureAsBytes).call()
    response_parsed = Web3.to_hex(response)

    if response_parsed != magic_value:
        raise 'Signature not verified'

    return True


class PaymentTransactionDetailsView(GenericViewSet):

    queryset = OrderPayment.objects.none()
    serializer_class = serializers.TransactionDetailsSerializer
    permission_classes = [permissions.AllowAny]
    permission = 'can_view_orders'
    write_permission = 'can_view_orders'

    def get_queryset(self):
        order = get_object_or_404(Order, code=self.kwargs['order'], event=self.request.event)
        return order.payments.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        try:
            sender_address = request.query_params['sender_address'].lower()
        except (KeyError, AttributeError):
            return HttpResponseBadRequest("Please supply sender_address GET.")

        has_other_unpaid_orders = SignedMessage.objects.filter(
            invalid=False,
            sender_address=sender_address,
            order_payment__state__in=(
                OrderPayment.PAYMENT_STATE_CREATED,
                OrderPayment.PAYMENT_STATE_PENDING
            )
        ).exists()

        response_data = serializer.data
        response_data["has_other_unpaid_orders"] = has_other_unpaid_orders

        return Response(response_data)

    def submit_signed_transaction(self, request, *args, **kwargs):
        order_payment: OrderPayment = self.get_object()
        serializer = self.get_serializer(order_payment)

        sender_address = request.data.get('selectedAccount').lower()
        signed_message = request.data.get('signedMessage')

        typed_data = serializer.data.get('message')
        typed_data['message']['sender_address'] = sender_address

        w3 = Web3(
            load_provider_from_uri(
                get_rpc_url_for_network(
                    order_payment.payment_provider,
                    serializer.data.get('network_identifier')
                )
            )
        )

        is_smart_contract_wallet = is_smart_contract(sender_address, w3)

        if is_smart_contract_wallet:
            message_hash = reconstruct_message_hash(
                typed_data['message']['sender_address'], typed_data['message']['receiver_address'], typed_data['message']['order_code'], typed_data['message']['chain_id'])
            validate_eip1271_signature(sender_address, signed_message, message_hash, w3)
        else:
            encoded_data = encode_structured_data(text=json.dumps(typed_data))
            recovered_address = w3.eth.account.recover_message(
                encoded_data, signature=signed_message)

            if recovered_address.lower() != sender_address.lower():
                raise

        transaction_hash = request.data.get('transactionHash').lower()
        message_obj = SignedMessage(
            signature=signed_message,
            raw_message=json.dumps(typed_data),
            sender_address=sender_address,
            recipient_address=serializer.data.get('recipient_address'),
            chain_id=serializer.data.get('chain_id'),
            order_payment=order_payment,
            transaction_hash=transaction_hash
        )
        message_obj.save()
        return Response(status=201)

    # Validates a signature against the order details adhering to EIP1271
    def validate_signature(self, request, *args, **kwargs):
        order_payment: OrderPayment = self.get_object()
        serializer = self.get_serializer(order_payment)

        signature = self.request.query_params.get('signature')
        sender_address = self.request.query_params.get('sender')

        typed_data = serializer.data.get('message')
        typed_data['message']['sender_address'] = sender_address

        w3 = Web3(
            load_provider_from_uri(
                get_rpc_url_for_network(
                    order_payment.payment_provider,
                    serializer.data.get('network_identifier')
                )
            )
        )

        message_hash = reconstruct_message_hash(
            typed_data['message']['sender_address'], typed_data['message']['receiver_address'], typed_data['message']['order_code'], typed_data['message']['chain_id'])

        # This will raise an exception if validation fails
        validate_eip1271_signature(sender_address, signature, message_hash, w3)

        return Response(status=200)


class OrderStatusView(mixins.RetrieveModelMixin, GenericViewSet):

    queryset = Order.objects.none()
    serializer_class = serializers.PaymentStatusSerializer
    permission_classes = [permissions.AllowAny]
    permission = 'can_view_orders'
    write_permission = 'can_view_orders'
    lookup_field = 'secret'

    def get_object(self):
        return get_object_or_404(Order, code=self.kwargs['order'], event=self.request.event)


class ERC20ABIView(APIView):

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(tokens.TOKEN_ABI)
