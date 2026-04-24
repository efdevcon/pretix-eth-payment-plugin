from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from . import __version__


class EthApp(AppConfig):
    name = 'pretix_eth'
    verbose_name = 'Pretix Crypto Payment (WalletConnect)'

    class PretixPluginMeta:
        name = _('Crypto payment (WalletConnect)')
        author = 'Ethereum Foundation'
        category = 'PAYMENT'
        description = _('Accept crypto payments (ETH, USDC, USDT0) via WalletConnect directly in Pretix checkout.')
        visible = True
        version = __version__

    def ready(self):
        from . import signals  # noqa
