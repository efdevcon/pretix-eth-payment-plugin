from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/wallet-address-upload/$",
        views.WalletAddressUploadView.as_view(),
        name="wallet_address_upload",
    ),
    url(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/wallet-address-upload/confirm/$",
        views.WalletAddressUploadConfirmView.as_view(),
        name="wallet_address_upload_confirm",
    ),
]
