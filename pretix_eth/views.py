from web3 import Web3
from eth_account.messages import encode_structured_data
from web3.providers.auto import load_provider_from_uri

from django.shortcuts import get_object_or_404

from pretix.base.models import Order, OrderPayment

from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework import permissions

from pretix_eth import serializers
from pretix_eth.utils import get_rpc_url_for_network


class PaymentTransactionDetailsView(GenericViewSet):

    queryset = OrderPayment.objects.none()
    serializer_class = serializers.TransactionDetailsSerializer
    permission_classes = [permissions.AllowAny]
    # permission = 'can_view_orders'
    # write_permission = 'can_view_orders'

    def get_queryset(self):
        order = get_object_or_404(Order, code=self.kwargs['order'], event=self.request.event)
        return order.payments.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def submit_signed_transaction(self, request, organizer, event, order, secret, pk):
        order_payment: OrderPayment = self.get_object()
        serializer = self.get_serializer(order_payment)
        # signable_message = encode_structured_data(
        #     text=serializer.data.get('message')
        # )
        # todo get message
        signed_message = request.data.get('signedMessage')
        sender_address = request.data.get('selectedAccount')

        # sign_mess2 = SignableMessage()
        w3 = Web3(
            load_provider_from_uri(
                get_rpc_url_for_network(
                    order_payment.payment_provider,
                    serializer.data.get('network_identifier')
                )
            )
        )
        recovered2 = w3.geth.personal.ecRecover(
            serializer.data.get('message'),
            signed_message
        )

        recovered_address = Web3().eth.account.recover_message(
            signable_message,
            signature=signed_message
        )

        if recovered_address.lower() != sender_address.lower():
            raise

        transaction_hash = request.data.get('transactionHash')
        # todo check signature
        # todo save transaction hash to model
        raise NotImplementedError()
