from datetime import timedelta

from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import NaturalTimeFormatter
from django.core.signing import BadSignature, TimestampSigner
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from pretix.control.views.event import EventSettingsViewMixin
from pretix.base.payment import OrderPayment
from pretix.api.views.order import OrderViewSet


from . import forms, models

from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action


""""
class ModelViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
"""


class PaymentTransactionDetailsView(GenericViewSet):

    queryset = OrderPayment.objects.get_queryset()
    serializer_class = None # todo
    permission = 'can_view_orders'
    write_permission = 'can_change_orders'

    def get_object(self):
        return super().get_object()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(methods=['post'], detail=True, url_path='signed', url_name='signed_transaction')
    def post_signed_transaction(self, request):
        return 'A'


class TransactionOrderViewSet(OrderViewSet):
    ...