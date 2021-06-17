from django.utils.translation import ugettext_lazy as _

ETH = "ETH"
DAI = "DAI"

class INetwork(object):
    """Interface that creates basic functionality to plug network into payments.py """
    def __init__(self, identifier):
        self.identifier = identifier
        eth_currency = f"{ETH}-{identifier}"
        dai_currency = f"{DAI}-{identifier}"
        self.eth_currency_choice = ((eth_currency, _(eth_currency)),)
        self.dai_currency_choice = ((dai_currency, _(dai_currency)),)

    def payment_instructions():
        raise NotImplementedError("This method has not been implemented for the network")


class Rinkeby(INetwork):
    """ Implementation for Rinkeby Testnet """
    def __init__(self):
        super(Rinkeby, self).__init__("Rinkeby")

class L1(INetwork):
    """ Implementation for Ethereum L1 """
    def __init__(self):
        super(L1, self).__init__("L1")

class ZkSync(INetwork):
    """ Implementation for ZkSync """
    def __init__(self):
        super(ZkSync, self).__init__("ZkSync")
        