from django.db import models

from pretix.base.models import (
    Event,
    OrderPayment,
)


class WalletAddress(models.Model):
    """
    Represents a wallet address to be used to receive an order payment.
    """
    hex_address = models.CharField(max_length=42, unique=True)

    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    order_payment = models.ForeignKey(OrderPayment, on_delete=models.PROTECT, null=True, blank=True)
