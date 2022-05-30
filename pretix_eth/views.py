from django.shortcuts import get_object_or_404

from pretix.base.models import Order, OrderPayment

from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from pretix_eth import serializers


class PaymentTransactionDetailsView(GenericViewSet):

    queryset = OrderPayment.objects.none()
    serializer_class = serializers.TransactionDetailsSerializer
    permission = 'can_view_orders'
    write_permission = 'can_change_orders'

    def get_queryset(self):
        order = get_object_or_404(Order, code=self.kwargs['order'], event=self.request.event)
        return order.payments.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def submit_signed_transaction(self, request):
        raise NotImplementedError()
