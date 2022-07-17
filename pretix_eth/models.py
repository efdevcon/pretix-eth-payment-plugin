from django.db import models
from django.utils import timezone

from pretix.base.models import OrderPayment


class SignedMessage(models.Model):

    MAX_AGE_UNCONFIRMED = 30 * 60  # allow retry payment after 30mins

    signature = models.CharField(max_length=132)
    raw_message = models.TextField()
    sender_address = models.CharField(max_length=42)
    recipient_address = models.CharField(max_length=42)
    chain_id = models.IntegerField()
    order_payment = models.ForeignKey(to=OrderPayment, on_delete=models.CASCADE, related_name='signed_messages')
    transaction_hash = models.CharField(max_length=66, null=True)
    invalid = models.BooleanField(default=False)
    created_at = models.DateTimeField(editable=False, null=True)

    def save(self, *args, **kwargs):
        if self.pk is None or self.created_at is None:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def invalidate(self):
        if not self.invalid:
            self.invalid = True
            self.save()

    @property
    def age(self):
        return timezone.now().timestamp() - self.created_at.timestamp()

    @property
    def another_signature_submitted(self):
        if self.order_payment is None:
            return False

        return SignedMessage.objects.filter(
            order_payment__order=self.order_payment.order,
            invalid=False
        ).exists()
