from django.db import models

from pretix.base.models import OrderPayment


class SignedMessage(models.Model):
    signature = models.CharField(max_length=132)
    raw_message = models.TextField()
    sender_address = models.CharField(max_length=42)
    recipient_address = models.CharField(max_length=42)
    chain_id = models.IntegerField()
    order_payment = models.ForeignKey(to=OrderPayment, on_delete=models.CASCADE, related_name='signed_messages')
    transaction_hash = models.CharField(max_length=66, null=True)
