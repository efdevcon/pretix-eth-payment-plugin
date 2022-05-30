from django.urls import re_path

from . import views

event_patterns = [
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/payment/(?P<pk>[0-9]+)/transaction_details/$',
        views.PaymentTransactionDetailsView.as_view({'get': 'retrieve', 'post': 'submit_signed_transaction'}),
        name='event.order.tranction_details'
    ),
]
