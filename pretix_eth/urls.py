from django.conf.urls import url, include
from django.urls import path
from pretix.multidomain import event_url
from .views import process_invoice, auth_start, redirect_view, pending
from . import views


urlpatterns = [
   url(r'^pretix_eth/', include([
    event_url(r'^pending/$', pending, name='pending'),
    event_url(r'^redirect/$', redirect_view, name='redirect', require_live=False),
    url(r'^return/(?P<order>[^/]+)/(?P<hash>[^/]+)/(?P<payment>[^/]+)/$', process_invoice, name='return'),
    ])),
 
#    event_url(r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/pretix_eth/pending/$', views.pending, name='pending'),
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/ethereum/connect/',
        auth_start, name='auth.start'),
]
