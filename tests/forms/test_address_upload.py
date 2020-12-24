import pytest

from pretix.base.models import (
    User, Team, Organizer, Event,
)

from django.core.files.uploadedfile import SimpleUploadedFile

from django.utils.timezone import now

from pretix_eth.models import WalletAddress


@pytest.fixture
def env(event, organizer):
    user = User.objects.create_user('admin@pretix', 'admin')
    t = Team.objects.create(organizer=event.organizer, can_view_orders=True, can_change_orders=True)
    t.members.add(user)
    t.limit_events.add(event)

    wallet_address = WalletAddress(
        hex_address='0x604Bcfb802b11866222825967aCD7Ec44d44168B', event=event)
    wallet_address.save()

    return organizer, event


@pytest.mark.django_db
def test_file_upload(client, env):
    client.login(email='admin@pretix', password='admin')

    organizer, event = env

    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    request_url = request_url.replace(' ', '%20')

    response = client.get(request_url)

    assert response.status_code == 200
    assert b'Wallet address upload' in response.content

    file = SimpleUploadedFile('upload.txt', """
        # OK
        0x38A670EB58F937D63D79D92dC651155595e66009
        # OK 
        0x26AA4d587584FE1f32707070768236eDC625dDD7
        # Duplicate
        0x26AA4d587584FE1f32707070768236eDC625dDD7
        # Commented
        # 0x0a648dD253CfBf0A7340C93fe7D8774FEfe972eD
        # Already exists in database
        0x604Bcfb802b11866222825967aCD7Ec44d44168B
    """.encode("utf-8"), content_type="text/plain")

    response = client.post(request_url, {'wallet_addresses': file}, follow=True)

    assert response.status_code == 200
    assert b'4 total addresses' in response.content
    assert b'3 unique addresses' in response.content
    assert b'1 addresses that already exist in the database' in response.content
    assert b'2 new addresses that don\'t already exist in the database' in response.content

    response = client.post(request_url + 'confirm/', {'action': 'confirm'}, follow=True)

    assert response.status_code == 200
    assert b'Created 2 new wallet addresses!' in response.content
