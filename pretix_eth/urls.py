from django.urls import path
from pretix.multidomain import event_url

from . import views

urlpatterns = views.webhook_patterns
