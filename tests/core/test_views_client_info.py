# tests/core/test_views_client_info.py
"""The wc_inject telemetry beacon (`client-info`).

phase=error carries what the wallet actually answered when a payment
failed (error name, numeric code, message, the checkout step), so a
failure like Trust Wallet's "An unknown RPC error occurred." can be read
from the server log instead of the buyer's browser console.
"""
import logging

import pytest
from django.test import RequestFactory

from pretix_eth.views import client_info


def _beacon(**params):
    request = RequestFactory().post('/plugin/wc/client-info/?' + '&'.join(f'{k}={v}' for k, v in params.items()))
    request.META['REMOTE_ADDR'] = '10.1.2.3'
    return client_info(request)


@pytest.mark.django_db
def test_error_phase_logs_wallet_error(caplog):
    with caplog.at_level(logging.INFO, logger='pretix_eth.views'):
        resp = _beacon(
            phase='error', order_code='TEST1', wallet_name='Trust%20Wallet', connection_kind='walletConnect',
            err_step='signing-tx', err_name='UnknownRpcError', err_code='-32000',
            err_msg='An%20unknown%20RPC%20error%20occurred.%20Details%3A%20Unknown%20method(s)%20requested',
        )
    assert resp.status_code == 204
    line = next(r.getMessage() for r in caplog.records if '[wc-client] phase=error' in r.getMessage())
    assert 'order=TEST1' in line
    assert 'err_step=signing-tx' in line
    assert 'err_name=UnknownRpcError' in line
    assert 'err_code=-32000' in line
    assert 'err_msg="An unknown RPC error occurred. Details: Unknown method(s) requested"' in line


@pytest.mark.django_db
def test_other_phases_carry_no_error_fields(caplog):
    with caplog.at_level(logging.INFO, logger='pretix_eth.views'):
        _beacon(phase='pay', order_code='TEST1', err_msg='ignored')
    line = next(r.getMessage() for r in caplog.records if '[wc-client] phase=pay' in r.getMessage())
    assert 'err_' not in line


@pytest.mark.django_db
def test_error_message_is_single_line_and_clipped(caplog):
    with caplog.at_level(logging.INFO, logger='pretix_eth.views'):
        _beacon(phase='error', order_code='TEST1', err_msg='line1%0Aline2%22quoted%22' + 'x' * 1000)
    line = next(r.getMessage() for r in caplog.records if '[wc-client] phase=error' in r.getMessage())
    assert '\n' not in line
    assert '"quoted"' not in line  # inner quotes neutralised so the quoted field stays parseable
    assert len(line) < 1200
