from django.db import models
from django.utils import timezone

from pretix.base.models import OrderPayment


class SignedMessage(models.Model):

    signature = models.CharField(max_length=132)
    raw_message = models.TextField()
    sender_address = models.CharField(max_length=42)
    recipient_address = models.CharField(max_length=42)
    chain_id = models.IntegerField()
    order_payment = models.ForeignKey(
        to=OrderPayment,
        on_delete=models.CASCADE,
        related_name='signed_messages',
    )
    transaction_hash = models.CharField(max_length=66, null=True, unique=True)
    safe_app_transaction_url = models.TextField(null=True, unique=True)
    invalid = models.BooleanField(default=False)
    created_at = models.DateTimeField(editable=False, null=True)
    is_confirmed = models.BooleanField(
        default=False)  # true for the payment that arrived

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


class WCPaymentAttempt(models.Model):
    """Tracks crypto payment attempts for the WalletConnect flow.
    Enforces one-time use of tx_hash to prevent cross-order replay."""
    STATE_CLAIMING = 'claiming'
    STATE_COMPLETED = 'completed'
    STATE_CHOICES = [
        (STATE_CLAIMING, 'claiming'),
        (STATE_COMPLETED, 'completed'),
    ]

    tx_hash = models.CharField(max_length=66, unique=True, db_index=True)
    quote_id = models.CharField(max_length=32, db_index=True)
    order_code = models.CharField(max_length=16)
    payer = models.CharField(max_length=42)
    chain_id = models.IntegerField()
    state = models.CharField(max_length=16, choices=STATE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'pretix_eth'


class X402PendingOrder(models.Model):
    """Pending x402 ticket order between purchase and payment verification."""
    event = models.ForeignKey('pretixbase.Event', on_delete=models.CASCADE, related_name='x402_pending_orders')
    payment_reference = models.CharField(max_length=100, primary_key=True)
    order_data = models.JSONField()
    total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    intended_payer = models.CharField(max_length=42)
    expected_eth_amount_wei_by_chain = models.JSONField(null=True, blank=True)
    expected_chain_id = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        app_label = 'pretix_eth'
        indexes = [models.Index(fields=['event', 'expires_at'])]


class X402CompletedOrder(models.Model):
    """Completed x402 ticket order after payment verification."""
    REFUND_PENDING = 'pending'
    REFUND_CONFIRMED = 'confirmed'
    REFUND_FAILED = 'failed'
    REFUND_CHOICES = [
        (REFUND_PENDING, 'pending'),
        (REFUND_CONFIRMED, 'confirmed'),
        (REFUND_FAILED, 'failed'),
    ]

    event = models.ForeignKey('pretixbase.Event', on_delete=models.CASCADE, related_name='x402_completed_orders')
    payment_reference = models.CharField(max_length=100, primary_key=True)
    tx_hash = models.CharField(max_length=66, unique=True, db_index=True)
    pretix_order_code = models.CharField(max_length=16, db_index=True)
    payer = models.CharField(max_length=42)
    completed_at = models.DateTimeField(auto_now_add=True)
    chain_id = models.IntegerField()
    total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    token_symbol = models.CharField(max_length=20)
    crypto_amount = models.CharField(max_length=50, null=True, blank=True)
    gas_cost_wei = models.CharField(max_length=50, null=True, blank=True)
    refund_status = models.CharField(max_length=16, null=True, blank=True, choices=REFUND_CHOICES, db_index=True)
    refund_tx_hash = models.CharField(max_length=66, null=True, blank=True)
    refund_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'pretix_eth'
        indexes = [
            models.Index(fields=['event', '-completed_at']),
            models.Index(fields=['event', 'refund_status']),
        ]


class X402VerifyAttempt(models.Model):
    """Rate-limit attempt log. Key is a prefix+identifier, e.g. verify_ref:<ref>, verify_ip:<ip>, purchase_ip:<ip>."""
    key = models.CharField(max_length=120, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'pretix_eth'
