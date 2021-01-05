import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from pretix_eth.models import WalletAddress


@pytest.fixture
def wallet_address(event):
    address = '0x604Bcfb802b11866222825967aCD7Ec44d44168B'
    WalletAddress.objects.create(hex_address=address, event=event)
    return address


@pytest.fixture
def admin_client(event, create_admin_client):
    return create_admin_client(event)


@pytest.mark.django_db
def test_file_upload_success(admin_client, organizer, event, wallet_address):
    existing_wallet_address = wallet_address
    assert WalletAddress.objects.all().count() == 1
    assert WalletAddress.objects.filter(hex_address=existing_wallet_address).exists()

    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    response = admin_client.get(request_url)

    assert response.status_code == 200
    assert b'Wallet address upload' in response.content

    file = SimpleUploadedFile('upload.txt', f"""
        # OK
        0x38A670EB58F937D63D79D92dC651155595e66009
        # OK
        0x26AA4d587584FE1f32707070768236eDC625dDD7
        # Duplicate
        0x26AA4d587584FE1f32707070768236eDC625dDD7
        # Commented
        # 0x0a648dD253CfBf0A7340C93fe7D8774FEfe972eD
        # Already exists in database
        {existing_wallet_address}
        # Weird spacing
            0x06E5c4854D7A21A4C466bcA74F6A2867a8ef0fd2
    """.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': file}, follow=True)

    assert response.status_code == 200
    assert b'5 total addresses' in response.content
    assert b'4 unique addresses' in response.content
    assert b'1 addresses that already exist in the database' in response.content
    assert b'3 new addresses that don\'t already exist in the database' in response.content

    response = admin_client.post(request_url + 'confirm/', {'action': 'confirm'}, follow=True)

    assert response.status_code == 200
    assert b'Created 3 new wallet addresses!' in response.content

    loaded_addresses = [
        '0x38A670EB58F937D63D79D92dC651155595e66009',
        '0x26AA4d587584FE1f32707070768236eDC625dDD7',
        '0x06E5c4854D7A21A4C466bcA74F6A2867a8ef0fd2'
    ]

    for address in loaded_addresses:
        assert WalletAddress.objects.filter(hex_address=address).exists()


@pytest.mark.django_db
def test_file_upload_length_short(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    invalid_file = SimpleUploadedFile('upload.txt', """
        0x38A670EB58F9D63D79D92dC651155595e66009
    """.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': invalid_file}, follow=True)
    assert response.status_code == 200
    assert b'Syntax error on line 1:' in response.content


@pytest.mark.django_db
def test_file_upload_length_long(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    invalid_file = SimpleUploadedFile('upload.txt', """
        0x38A670EB58F9D63Dfds32D279D92dC651155595e66009
    """.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': invalid_file}, follow=True)
    assert response.status_code == 200
    assert b'Syntax error on line 1:' in response.content


@pytest.mark.django_db
def test_file_upload_one_address_per_line(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    invalid_file = SimpleUploadedFile('upload.txt', """
        # Two addresses in the same line, expected one
        0xe61407b0708CC10006aAc0ceA62F553Ed84D2aD8 0xcD9989Dc8F0f02866eC945cBCCDd6CFA32D46026
    """.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': invalid_file}, follow=True)
    assert response.status_code == 200
    assert b'Syntax error on line 1:' in response.content


@pytest.mark.django_db
def test_file_upload_invalid_middle(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    invalid_file = SimpleUploadedFile('upload.txt', """
        # Invalid address in the middle of the file
        0xe61407b0708CC10006aAc0ceA62F553Ed84D2aD8
        0x378c3Ba28099187788500cb4a833FbA161F9879C
        0xcD9989Dc8F0f02866eC9BCCDd6CFA32D46026
        0x1F59154Bcf62A3B63Db28F306996540c0a6aD8a5
    """.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': invalid_file}, follow=True)
    assert response.status_code == 200
    assert b'Syntax error on line 3:' in response.content


@pytest.mark.django_db
def test_file_upload_invalid_prefix(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    invalid_file = SimpleUploadedFile('upload.txt', """
        # Prefix is not 0x
        e61407b0708CC10006aAc0ceA62F553Ed84D2aD8
    """.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': invalid_file}, follow=True)
    assert response.status_code == 200
    assert b'Syntax error on line 1:' in response.content


@pytest.mark.django_db
def test_file_upload_empty_file(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    empty_file = SimpleUploadedFile('upload.txt', ''.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': empty_file}, follow=True)
    assert response.status_code == 200
    assert b'The submitted file is empty.' in response.content


@pytest.mark.django_db
def test_file_upload_no_addresses_in_file(admin_client, organizer, event):
    request_url = f'/control/event/{organizer.slug}/{event.slug}/wallet-address-upload/'
    no_address_file = SimpleUploadedFile(
        'upload.txt', '#'.encode("utf-8"), content_type="text/plain")

    response = admin_client.post(request_url, {'wallet_addresses': no_address_file}, follow=True)
    assert response.status_code == 200
    assert b'File contains no addresses' in response.content
