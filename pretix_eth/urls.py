from django.conf.urls import include, re_path

from pretix.api.urls import event_router

from . import views

event_router.register(r'transaction_details', views.PaymentTransactionDetailsView)
event_router.register(r'order2', views.OrderViewSet)

url_patters = [
    re_path(r'^organizers/(?P<organizer>[^/]+)/events2/(?P<event>[^/]+)/', include(event_router.urls)),

]
