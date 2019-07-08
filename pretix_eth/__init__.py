from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy


class PluginApp(AppConfig):
    name = 'pretix_eth'
    verbose_name = 'Pretix Ethereum Payment Provider'

    class PretixPluginMeta:
        name = ugettext_lazy('Pretix Ethereum Payment Provider')
        author = 'Victor(https://github.com/vic-en)'
        description = ugettext_lazy('An ethereum payment provider plugin for pretix software')
        visible = True
        version = '1.0.1'

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_eth.PluginApp'
