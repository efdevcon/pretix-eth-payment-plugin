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
from pytest_django.fixtures import (
    _disable_native_migrations,
)

from pretix_eth.payment import Ethereum
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
    provider = Ethereum(event)
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
                'provider': 'ethereum'
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


@pytest.fixture(scope="function")
def django_db_setup(
    request,
    django_test_environment,
    django_db_blocker,
    django_db_use_migrations,
    django_db_keepdb,
    django_db_createdb,
    django_db_modify_db_settings,
):
    """
    Copied and pasted from here:
    https://github.com/pytest-dev/pytest-django/blob/d2973e21c34d843115acdbccdd7a16cb2714f4d3/pytest_django/fixtures.py#L84

    We override this fixture and give it a "function" scope as a hack to force
    the test database to be re-created per test case.  This causes the same
    database ids to be used for payment records in each test run.  Usage of the
    `reset_sequences` flag provided by pytest-django isn't always sufficient
    since it can depend on whether or not a particular database supports
    sequence resets.

    As an example of why sequence resets are necessary, tests in the
    `tests.integration.test_confirm_payments` module will fail if database ids
    are not reset per test function.  This is because the test wallet on the
    Goerli test net must hardcode payment ids into transactions and token
    transfers.  If payment ids don't deterministically begin at 1 per test
    case, payment ids in the Goerli test wallet won't correctly correspond to
    payment ids generated during test runs.
    """
    from pytest_django.compat import setup_databases, teardown_databases

    setup_databases_args = {}

    if not django_db_use_migrations:
        _disable_native_migrations()

    if django_db_keepdb and not django_db_createdb:
        setup_databases_args["keepdb"] = True

    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            **setup_databases_args
        )

    def teardown_database():
        with django_db_blocker.unblock():
            try:
                teardown_databases(db_cfg, verbosity=request.config.option.verbose)
            except Exception as exc:
                request.node.warn(
                    pytest.PytestWarning(
                        "Error when trying to teardown test databases: %r" % exc
                    )
                )

    if not django_db_keepdb:
        request.addfinalizer(teardown_database)


def pytest_addoption(parser):
    parser.addoption(
        "--require-web3", action="store_true", default=False,
        help="run integration tests that need web3 provider",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "require-web3: mark test as one that requires web3 provider")
