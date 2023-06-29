from django.apps import AppConfig
from django.utils.translation import gettext_lazy


class PluginApp(AppConfig):
    name = 'pretix_eth'
    verbose_name = 'Pretix Ethereum Payment Provider'

    class PretixPluginMeta:
        name = gettext_lazy('Pretix Ethereum Payment Provider')
        author = 'Pretix Ethereum Payment Plugin Contributors'
        category = 'PAYMENT'
        description = gettext_lazy('An ethereum payment provider plugin for pretix software')
        visible = True
        version = '2.0.6-dev'

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_eth.PluginApp'
