from django.utils.translation import ugettext_lazy as _

ETH = "ETH"
DAI = "DAI"

class INetwork(object):
    """Interface that creates basic functionality to plug network into payments.py """
    def __init__(self, identifier):
        self.identifier = identifier
        self.currency_type_choices = ()
        eth_currency = f"{ETH}-{identifier}"
        dai_currency = f"{DAI}-{identifier}"
        self.currency_type_choices += ((eth_currency, _(eth_currency)),)
        self.currency_type_choices += ((dai_currency, _(dai_currency)),)

    def payment_instructions():
        raise NotImplementedError("This method has not been implemented for the network")


class Rinkeby(INetwork):
    """ Implementation for Rinkeby Testnet """
    def __init__(self):
        super(Rinkeby, self).__init__("Rinkeby")

class ZkSync(INetwork):
    """ Implementation for ZkSync """
    def __init__(self):
        super(ZkSync, self).__init__("ZkSync")
        