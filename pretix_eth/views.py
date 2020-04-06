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

from . import forms, models


UPLOAD_ADDRESS_KEY = "pretix_eth_upload_addresses"
UPLOAD_VALID_DURATION = timedelta(minutes=5)


class WalletAddressUploadView(EventSettingsViewMixin, FormView):
    form_class = forms.WalletAddressUploadForm
    template_name = 'pretix_eth/wallet_address_upload.html'
    permission = 'can_change_event_settings'

    def form_valid(self, form):
        file_addresses = form.cleaned_data["wallet_addresses"]

        now = timezone.now()
        expire_time = now + UPLOAD_VALID_DURATION
        signer = TimestampSigner()
        signed_file_addresses = signer.sign(file_addresses)

        self.request.session[UPLOAD_ADDRESS_KEY] = signed_file_addresses

        messages.success(
            self.request,
            _(
                'Successfully parsed {n} wallet addresses.  '
                'You have until {expire_time} to confirm your address upload.'
            ).format(
                n=len(file_addresses.splitlines()),
                expire_time=NaturalTimeFormatter.string_for(expire_time),
            ),
        )

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)

    def get_success_url(self, **kwargs):
        return reverse('plugins:pretix_eth:wallet_address_upload_confirm', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
        })


class AddressUploadSessionError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class WalletAddressUploadConfirmView(EventSettingsViewMixin, FormView):
    form_class = forms.WalletAddressUploadConfirmForm
    template_name = 'pretix_eth/wallet_address_upload_confirm.html'
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except AddressUploadSessionError as e:
            return e.response

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AddressUploadSessionError as e:
            return e.response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        file_addresses = self.get_file_addresses()
        hex_addresses = file_addresses.splitlines()
        hex_address_set = set(hex_addresses)
        existing_addresses = models.WalletAddress.objects.filter(hex_address__in=hex_address_set)
        existing_address_set = set(existing_addresses.values_list("hex_address", flat=True))
        new_addresses = hex_address_set - existing_address_set

        ctx["file_address_count"] = len(hex_addresses)
        ctx["unique_address_count"] = len(hex_address_set)
        ctx["existing_address_count"] = existing_addresses.count()
        ctx["new_address_count"] = len(new_addresses)

        return ctx

    def form_valid(self, form):
        file_addresses = self.get_file_addresses()
        return self.session_key_valid(form, file_addresses)

    def session_key_valid(self, form, file_addresses):
        action = form.cleaned_data["action"]

        if action == "cancel":
            messages.info(self.request, _('Wallet address upload cancelled.'))
            return self.clear_and_start_over()

        file_addresses = self.get_file_addresses()
        hex_addresses = file_addresses.splitlines()
        hex_address_set = set(hex_addresses)
        existing_addresses = models.WalletAddress.objects.filter(hex_address__in=hex_address_set)
        existing_address_set = set(existing_addresses.values_list("hex_address", flat=True))
        new_addresses = hex_address_set - existing_address_set

        created = models.WalletAddress.objects.bulk_create([
            models.WalletAddress(
                hex_address=hex_address,
                event=self.request.event,
            )
            for hex_address in new_addresses
        ])

        messages.success(
            self.request,
            _('Created {n} new wallet addresses!').format(n=len(created)),
        )
        return self.clear_and_start_over()

    def get_file_addresses(self):
        try:
            signed_file_addresses = self.request.session[UPLOAD_ADDRESS_KEY]
        except KeyError:
            raise AddressUploadSessionError(
                "no session key",
                response=self.no_session_key(),
            )
        signer = TimestampSigner()
        try:
            file_addresses = signer.unsign(signed_file_addresses, max_age=UPLOAD_VALID_DURATION)
        except BadSignature:
            raise AddressUploadSessionError(
                "session key expired",
                response=self.session_key_expired(),
            )
        return file_addresses

    def clear_session_key(self):
        del self.request.session[UPLOAD_ADDRESS_KEY]

    def clear_and_start_over(self):
        self.clear_session_key()
        return redirect(self.get_success_url())

    def no_session_key(self):
        return redirect(self.get_success_url())

    def session_key_expired(self):
        messages.error(self.request, _('Wallet address upload expired! Please try again.'))
        return self.clear_and_start_over()

    def form_invalid(self, form):
        messages.error(self.request, _('Unrecognized action. Please try again.'))
        return self.clear_and_start_over()

    def get_success_url(self, **kwargs):
        return reverse('plugins:pretix_eth:wallet_address_upload', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
        })
