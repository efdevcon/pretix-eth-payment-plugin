# tests/core/test_sanctions.py
"""OFAC / scam-list screening (pretix_eth/sanctions.py).

The module must never fail closed on infrastructure (list fetch or Django
cache being down must not block checkout) and never fail open on a known
sanctioned address (the bundled snapshot guarantees a floor).
"""
import pytest

from pretix_eth import sanctions

# An address from the bundled OFAC snapshot (Tornado Cash was DELISTED in
# March 2025, so don't use those). If the SDN list ever drops this one too,
# swap in any current entry from `_OFAC_FALLBACK` — the assertions below only
# need "a bundled address" and "a known-clean address".
SANCTIONED = '0x0330070fd38ec3bb94f58fa55d40368271e9e54a'
CLEAN = '0x403a3a81aba974deb4faf20514ae34faf9268e28'


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Reset the module memo and make the Django cache a no-op so tests
    exercise the fetch/fallback logic deterministically."""
    monkeypatch.setattr(sanctions, '_memo', {'ofac': None, 'ofac_at': 0.0, 'scam': None, 'scam_at': 0.0})

    class BrokenCache:
        def get(self, *a, **k):
            raise RuntimeError('cache down')

        def set(self, *a, **k):
            raise RuntimeError('cache down')

    monkeypatch.setattr(sanctions, '_cache', lambda: BrokenCache())


def test_bundled_fallback_used_when_fetch_fails(monkeypatch):
    def boom():
        raise OSError('network down')

    monkeypatch.setattr(sanctions, '_fetch_ofac_union', boom)
    assert sanctions.is_sanctioned(SANCTIONED) is True
    assert sanctions.is_sanctioned(CLEAN) is False


def test_is_sanctioned_normalizes_case_and_whitespace(monkeypatch):
    monkeypatch.setattr(sanctions, '_fetch_ofac_union', lambda: frozenset([SANCTIONED]))
    assert sanctions.is_sanctioned(SANCTIONED.upper().replace('0X', '0x'))
    assert sanctions.is_sanctioned(f'  {SANCTIONED}  ')
    assert not sanctions.is_sanctioned(None)
    assert not sanctions.is_sanctioned('')


def test_fresh_fetch_wins_over_fallback(monkeypatch):
    extra = '0x' + 'ab' * 20
    monkeypatch.setattr(sanctions, '_fetch_ofac_union', lambda: frozenset([extra]))
    assert sanctions.is_sanctioned(extra) is True
    # memoized within the freshness window: second call must not refetch
    monkeypatch.setattr(sanctions, '_fetch_ofac_union', lambda: (_ for _ in ()).throw(AssertionError('refetched')))
    assert sanctions.is_sanctioned(extra) is True


def test_scam_list_fails_open(monkeypatch):
    import requests

    def boom(*a, **k):
        raise OSError('network down')

    monkeypatch.setattr(requests, 'get', boom)
    assert sanctions.is_scam_flagged(SANCTIONED) is False
