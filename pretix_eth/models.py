from django.db import models

from pretix.base.models import OrderPayment


class SignedMessage(models.Model):
    signature = models.CharField(max_length=132)
    raw_message = models.CharField(max_length=256)
    sender_address = models.CharField(max_length=42)
    recipient_address = models.CharField(max_length=42)
    chain_id = models.SmallIntegerField()
    order_payment = models.ForeignKey(to=OrderPayment, on_delete=models.CASCADE, related_name='signed_messages')
