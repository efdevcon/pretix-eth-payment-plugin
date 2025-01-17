from django.urls import path

from . import views

event_patterns = []
urlpatterns = views.webhook_patterns
