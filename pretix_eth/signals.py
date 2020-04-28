from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django.template.loader import get_template
from django import forms

from pretix.base.middleware import _parse_csp, _merge_csp, _render_csp
from pretix.presale.signals import (
    html_head,
    question_form_fields,
    process_response,
)
from pretix.base.signals import register_payment_providers
from pretix.control.signals import nav_event_settings


NFT_QUESTION_IDENTIFIER = 'eth-payment-plugin-nft-address'
PAYMENT_ETH_INFO_CLASS = 'payment_eth_info'
PAYMENT_ETH_INFO_NAME = 'payment_eth_info'


@receiver(process_response, dispatch_uid="payment_eth_add_question_type_csp")
def signal_process_response(sender, request, response, **kwargs):
    url = resolve(request.path_info) # TODO: enable js only when question is asked
    h = {}
    if 'Content-Security-Policy' in response:
        h = _parse_csp(response['Content-Security-Policy'])
    _merge_csp(h, {
        'style-src': [
            "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='",
            "'sha256-O+AX3tWIOimhuzg+lrMfltcdtWo7Mp2Y9qJUkE6ysWE='",
        ],
        'manifest-src': ["'self'"],
    })
    response['Content-Security-Policy'] = _render_csp(h)
    return response

@receiver(html_head, dispatch_uid="payment_eth_add_question_type_javascript")
def add_question_type_javascript(sender, request, **kwargs):
    url = resolve(request.path_info) # TODO: enable js only when question is asked
    template = get_template('pretix_eth/question_type_javascript.html')
    context = {
        'event': sender,
    }
    return template.render(context)

@receiver(question_form_fields, dispatch_uid="payment_eth_add_question_type_form_field")
def mark_question_type(sender, position, **kwargs):
    questions = sender.questions.filter(identifier=NFT_QUESTION_IDENTIFIER)
    question_ids = [ 'id_{p.id}-question_{q.id}'.format(p=position, q=q) for q in questions ]
    payment_eth_info_widget = forms.HiddenInput(attrs={
        'value': ','.join(question_ids),
        'class': PAYMENT_ETH_INFO_CLASS,
    })
    payment_eth_info_field = forms.CharField(
        label='Payment ETH Info',
        max_length=100,
        widget=payment_eth_info_widget,
        required=False,
    )
    return {
        PAYMENT_ETH_INFO_NAME: payment_eth_info_field,
    }

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
