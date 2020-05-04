from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.signals import logentry_display, register_payment_providers
from pretix.control.signals import nav_event_settings


@receiver(register_payment_providers, dispatch_uid="payment_eth")
def register_payment_provider(sender, **kwargs):
    from .payment import Ethereum
    return Ethereum


@receiver(nav_event_settings, dispatch_uid='pretix_eth_nav_wallet_address_upload')
def navbar_wallet_address_upload(sender, request, **kwargs):
    url = resolve(request.path_info)
    return [{
        'label': _('Wallet address upload'),
        'url': reverse('plugins:pretix_eth:wallet_address_upload', kwargs={
            'event': request.event.slug,
            'organizer': request.organizer.slug,
        }),
        'active': (
            url.namespace == 'plugins:pretix_eth'
            and (
                url.url_name == 'wallet_address_upload'
                or url.url_name == 'wallet_address_upload_confirm'
            )
        ),
    }]


@receiver(signal=logentry_display)
def wallet_address_upload_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type == 'pretix_eth.wallet_address_upload':
        data = logentry.parsed_data
        return _(
            'Uploaded {file_address_count} addresses '
            'with {new_address_count} new addresses '
            'and {existing_address_count} existing addresses.'
        ).format(
            file_address_count=data['file_address_count'],
            new_address_count=data['new_address_count'],
            existing_address_count=data['existing_address_count'],
        )
