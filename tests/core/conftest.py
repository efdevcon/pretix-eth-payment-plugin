import datetime

from django.utils import timezone

import pytest

from pretix.base.models import (
    Event,
    Organizer,
)

from pretix_eth.payment import Ethereum


ETH_ADDRESS = '0xeee0123400000000000000000000000000000000'
DAI_ADDRESS = '0xda10123400000000000000000000000000000000'


@pytest.fixture
def event(transactional_db):
    now = timezone.now()
    presale_start_at = now + datetime.timedelta(days=2)
    presale_end_at = now + datetime.timedelta(days=6)
    start_at = now + datetime.timedelta(days=7)
    end_at = now + datetime.timedelta(days=14)

    organizer = Organizer.objects.create(
        name='Ethereum Foundation',
        slug='ethereum-foundation',
    )
    event = Event.objects.create(
        name='Devcon',
        slug='devcon',
        organizer=organizer,
        date_from=start_at,
        date_to=end_at,
        presale_start=presale_start_at,
        presale_end=presale_end_at,
        location='Osaka',
    )
    return event


@pytest.fixture
def provider(event):
    provider = Ethereum(event)
    return provider
