from django.urls import path, re_path

from . import views

event_patterns = [
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/payment/(?P<pk>[0-9]+)/transaction_details/$',
        views.PaymentTransactionDetailsView.as_view({'get': 'retrieve', 'post': 'submit_signed_transaction'}),
        name='event.order.transaction_details'
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/status/$',
        views.OrderStatusView.as_view({'get': 'retrieve'}),
        name='event.order.payment_status'
    ),

    path('erc20_abi', views.ERC20ABIView.as_view(), name='erc2O_abi')
]
