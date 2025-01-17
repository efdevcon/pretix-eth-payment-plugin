import datetime
import decimal
import contextlib
from packaging import version

from django.utils import timezone
import pretix
from pretix.base.models import (
    Event,
    Organizer,
)
from pretix.base.models import (
    Order,
    OrderPayment,
    User,
    Team,
)
import pytest

from pretix_eth.payment import DaimoPay
from rest_framework.test import APIClient


@pytest.fixture
def organizer(django_db_reset_sequences):
    return Organizer.objects.create(
        name='Ethereum Foundation',
        slug='ef',
    )


@pytest.fixture
def event(django_db_reset_sequences, organizer):
    now = timezone.now()

    presale_start_at = now + datetime.timedelta(days=2)
    presale_end_at = now + datetime.timedelta(days=6)
    start_at = now + datetime.timedelta(days=7)
    end_at = now + datetime.timedelta(days=14)

    event = Event.objects.create(
        name='Devcon',
        slug='devcon',
        organizer=organizer,
        date_from=start_at,
        date_to=end_at,
        presale_start=presale_start_at,
        presale_end=presale_end_at,
        location='Osaka',
        plugins='pretix_eth',
    )

    return event


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def create_admin_client():
    def _create_event_admin(event, email='admin@example.com'):
        user = User.objects.create_user(email=email, password='admin')
        team = Team.objects.create(organizer=event.organizer,
                                   can_view_orders=True, can_change_orders=True)
        team.members.add(user)
        team.limit_events.add(event)

        client = APIClient()
        client.login(email='admin@example.com', password='admin')
        return client

    return _create_event_admin


@pytest.fixture
def provider(event):
    provider = DaimoPay(event)
    return provider


@pytest.fixture
def get_organizer_scope(organizer):
    if version.parse(pretix.__version__) >= version.parse('3.0.0'):
        # If pretix>=3.0.0, we must scope certain database queries explicitly
        from django_scopes import scope

        return lambda: scope(organizer=organizer)
    else:
        # Otherwise, the scope manager is just a no-op
        @contextlib.contextmanager
        def noop_scope():
            yield

        return noop_scope


@pytest.fixture
def get_order_and_payment(django_db_reset_sequences, event, get_organizer_scope):
    def _get_order_and_payment(order_kwargs=None, payment_kwargs=None, info_data=None):
        with get_organizer_scope():
            # Create order
            final_order_kwargs = {
                'event': event,
                'email': 'test@example.com',
                'locale': 'en_US',
                'datetime': timezone.now(),
                'total': decimal.Decimal('100.00'),
                'status': Order.STATUS_PENDING,
            }
            if order_kwargs is not None:
                final_order_kwargs.update(order_kwargs)
            order = Order.objects.create(**final_order_kwargs)

            # Create payment
            final_payment_kwargs = {
                'amount': '100.00',
                'state': OrderPayment.PAYMENT_STATE_PENDING,
                'provider': 'daimo_pay'
            }
            if payment_kwargs is not None:
                final_payment_kwargs.update(payment_kwargs)
            final_payment_kwargs['order'] = order
            payment = OrderPayment.objects.create(**final_payment_kwargs)

            # Add payment json data if provided
            if info_data is not None:
                payment.info_data = info_data
                payment.save(update_fields=['info'])

        return order, payment

    return _get_order_and_payment


def pytest_addoption(parser):
    parser.addoption(
        "--require-web3", action="store_true", default=False,
        help="run integration tests that need web3 provider",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "require-web3: mark test as one that requires web3 provider")
