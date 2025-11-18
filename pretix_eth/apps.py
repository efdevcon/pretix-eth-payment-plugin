from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from . import __version__


class EthApp(AppConfig):
    name = 'pretix_eth'
    verbose_name = 'Pretix Ethereum Payment Provider'

    class PretixPluginMeta:
        name = _('Pretix Ethereum Payment Provider')
        author = 'Pretix Ethereum Payment Plugin Contributors'
        category = 'PAYMENT'
        description = _('An ethereum payment provider plugin for pretix software')
        visible = True
        version = __version__

    def ready(self):
        from . import signals  # NOQA
