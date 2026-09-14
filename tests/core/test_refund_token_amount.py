# tests/core/test_refund_token_amount.py
"""`derive_token_amount` sizes the crypto figure of a refund from the payment
itself: the same share of the raw on-chain amount as the refund is of the
USD paid, integer math rounding down. It must match what the devcon admin
panel sends on-chain (same formula), return the whole amount for a full
refund, and give up cleanly on rows without the figures."""
from decimal import Decimal

from pretix_eth.x402.pretix_client import derive_token_amount


def test_partial_refund_is_the_matching_share_of_the_payment():
    # 25 tickets paid with 4.51256828 ETH, 2 canceled: 698 of 8725 USD → 8 %.
    info = {'amount': '4512568280000000000', 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('8725.00'), '698.00') == ('361005462400000000', 'ETH')


def test_second_partial_refund_uses_the_original_payment_as_base():
    info = {'amount': '4512568280000000000', 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('8725.00'), '349.00') == ('180502731200000000', 'ETH')


def test_full_refund_returns_the_exact_amount_sent():
    info = {'amount': '10690000000000', 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('0.02'), '0.02') == ('10690000000000', 'ETH')
    # Refund above the payment (cancellation fee edge) still caps at what was sent.
    assert derive_token_amount(info, Decimal('0.02'), '0.05') == ('10690000000000', 'ETH')


def test_dust_payment_half_refund():
    info = {'amount': '10690000000000', 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('0.02'), '0.01') == ('5345000000000', 'ETH')


def test_legacy_raw_suffix_and_usdc_units():
    info = {'amount': '374100000 (raw)', 'token_symbol': 'USDC'}
    assert derive_token_amount(info, '374.10', '25.00') == ('25000000', 'USDC')


def test_missing_or_bad_figures_give_none():
    assert derive_token_amount({}, Decimal('10'), '5') == (None, None)
    assert derive_token_amount({'amount': 'abc', 'token_symbol': 'ETH'}, Decimal('10'), '5') == (None, None)
    assert derive_token_amount({'amount': '100', 'token_symbol': 'ETH'}, Decimal('0'), '5') == (None, None)
    assert derive_token_amount({'amount': '100', 'token_symbol': 'ETH'}, Decimal('10'), '0') == (None, None)
