from django.db import (
    models,
    transaction,
)
from pretix.base.models import (
    Event,
    OrderPayment,
    OrderRefund,
)


class WalletAddressError(Exception):
    pass


class WalletAddressQuerySet(models.QuerySet):
    def for_event(self, event: Event) -> models.QuerySet:
        return self.filter(event=event)

    def unused(self) -> models.QuerySet:
        return self.filter(order_payment__isnull=True)

    def unconfirmed_orders(self) -> models.QuerySet:
        return self.filter(order_payment__state__in=(
            OrderPayment.PAYMENT_STATE_CREATED,
            OrderPayment.PAYMENT_STATE_PENDING,
        ))

    def unconfirmed_refunds(self) -> models.QuerySet:
        orders_awaiting_refund = OrderRefund.objects.filter(
            state=OrderRefund.REFUND_STATE_CREATED).values_list('order', flat=True)

        return self.filter(order_payment_id__in=(orders_awaiting_refund))


class WalletAddressManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return WalletAddressQuerySet(self.model, using=self._db)

    def get_for_order_payment(self, order_payment: OrderPayment) -> 'WalletAddress':
        event = order_payment.order.event
        unused_addresses = self.select_for_update().unused().for_event(event)

        with transaction.atomic():
            if order_payment.walletaddress_set.exists():
                address = order_payment.walletaddress_set.first()
            else:
                if not unused_addresses.exists():
                    raise WalletAddressError(
                        "No wallet addresses remain that haven't been used",
                    )
                address = unused_addresses.first()
                address.order_payment = order_payment
                address.save()

        return address


class WalletAddress(models.Model):
    """
    Represents a wallet address to be used to receive an order payment.
    """
    hex_address = models.CharField(max_length=42, unique=True)

    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    order_payment = models.ForeignKey(
        OrderPayment, on_delete=models.CASCADE, null=True, blank=True
    )

    objects = WalletAddressManager()
