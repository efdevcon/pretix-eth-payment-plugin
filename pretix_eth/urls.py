from django.urls import path
from pretix.multidomain import event_url

from . import views

event_patterns = [
    event_url(r'^pay/', views.refund_frontend_view, name='frontend'),
]

urlpatterns = views.webhook_patterns
