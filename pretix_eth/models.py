from django.db import models

from pretix.base.models import (
    OrderPayment,
)


class Transaction(models.Model):
    """
    Represents a transaction that has been submitted by a ticket buyer as
    proof of payment. Storing this information allows us to prevent the same
    transaction from being used more than once for payment.
    """
    txn_hash = models.CharField(max_length=66, unique=True)
    order_payment = models.ForeignKey(OrderPayment, on_delete=models.PROTECT)
