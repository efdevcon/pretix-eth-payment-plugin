# tests/core/test_refund_token_amount.py
"""`derive_token_amount` sizes the crypto figure of a refund from the payment
itself: the same share of the raw on-chain amount as the refund is of the
USD paid, integer math rounding down. It must match what the devcon admin
panel sends on-chain (same formula), return the whole amount for a full
refund, and give up cleanly on rows without the figures."""
from decimal import Decimal

from pretix_eth.x402.pretix_client import derive_token_amount

# A 1000 USD order paid with 0.5 ETH (2000 USD/ETH).
HALF_ETH = '500000000000000000'


def test_partial_refund_is_the_matching_share_of_the_payment():
    # 80 USD of positions canceled → 8 % of the ETH received.
    info = {'amount': HALF_ETH, 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('1000.00'), '80.00') == ('40000000000000000', 'ETH')


def test_second_partial_refund_uses_the_original_payment_as_base():
    info = {'amount': HALF_ETH, 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('1000.00'), '40.00') == ('20000000000000000', 'ETH')


def test_full_refund_returns_the_exact_amount_sent():
    info = {'amount': HALF_ETH, 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('1000.00'), '1000.00') == (HALF_ETH, 'ETH')
    # Refund above the payment (cancellation fee edge) still caps at what was sent.
    assert derive_token_amount(info, Decimal('1000.00'), '1200.00') == (HALF_ETH, 'ETH')


def test_rounds_down_to_the_base_unit():
    # 1 USD of a 3 USD payment made with 100 wei → 33 wei, never 34.
    info = {'amount': '100', 'token_symbol': 'ETH'}
    assert derive_token_amount(info, Decimal('3.00'), '1.00') == ('33', 'ETH')


def test_legacy_raw_suffix_and_usdc_units():
    info = {'amount': '374100000 (raw)', 'token_symbol': 'USDC'}
    assert derive_token_amount(info, '374.10', '25.00') == ('25000000', 'USDC')


def test_missing_or_bad_figures_give_none():
    assert derive_token_amount({}, Decimal('10'), '5') == (None, None)
    assert derive_token_amount({'amount': 'abc', 'token_symbol': 'ETH'}, Decimal('10'), '5') == (None, None)
    assert derive_token_amount({'amount': '100', 'token_symbol': 'ETH'}, Decimal('0'), '5') == (None, None)
    assert derive_token_amount({'amount': '100', 'token_symbol': 'ETH'}, Decimal('10'), '0') == (None, None)
