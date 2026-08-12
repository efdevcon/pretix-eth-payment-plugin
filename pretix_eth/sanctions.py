"""OFAC (and scam-list) screening for EVM addresses.

Used to refuse doing business with sanctioned addresses:

  * WC buyer flow: `create_quote` refuses to mint a quote for a sanctioned
    payer, and the verify/settlement path re-checks before confirming (the
    list may have been updated between quote and settle).
  * Admin refunds: refuse to send funds TO a sanctioned address (issuing a
    refund to a sanctioned address is itself a violation — freeze the order
    and escalate instead), and warn/block on community scam-list hits.

List source: github.com/0xB10C/ofac-sanctioned-digital-currency-addresses,
regenerated daily from the US Treasury SDN list. OFAC tags each address with
the asset ticker it was reported under, but an EVM address is the same
keypair on every chain — so we union every ticker list that contains 0x
addresses (the ETH file alone misses addresses listed only under
ARB/USDC/USDT/BSC/ETC). Same source as devcon's `src/scripts/ofac-scan.ts`.

Availability: the fetched union is cached (Django cache) for 24h, a last-good
copy is kept without expiry, and a static snapshot is bundled below — so
screening never fails open to "unknown", and a GitHub outage never blocks
checkout. The bundled snapshot only grows monotonically stale; the fetch
refreshes it whenever it succeeds.

The ScamSniffer community blacklist (refund warnings only, NOT used for buyer
screening: false positives there would block legitimate buyers) is fetched
the same way but has no bundled fallback — on total fetch failure scam
screening fails open (returns False) with a loud log line.
"""
import logging
import threading
import time

log = logging.getLogger(__name__)

_OFAC_EVM_TICKERS = ('ETH', 'ARB', 'USDC', 'USDT', 'BSC', 'ETC')
_OFAC_URL = ('https://raw.githubusercontent.com/0xB10C/'
             'ofac-sanctioned-digital-currency-addresses/lists/'
             'sanctioned_addresses_{ticker}.txt')
_SCAM_URL = ('https://raw.githubusercontent.com/scamsniffer/'
             'scam-database/main/blacklist/address.json')

_CACHE_FRESH_SECONDS = 24 * 3600
# After a FAILED refresh, retry this soon instead of pinning the fallback for
# a full freshness window — a single GitHub blip must not degrade screening
# to the bundled snapshot (or disable scam checks) for 24h.
_FAILURE_RETRY_SECONDS = 300
# Short timeout: these fetches sit on the buyer checkout path (create_quote /
# verify) when caches are cold. 6 tickers x this timeout is the worst-case
# inline stall for the ONE request that does the refresh.
_FETCH_TIMEOUT = 5

# Single-flight: only one thread per process refreshes; everyone else serves
# whatever they have (stale memo, last-good cache, bundled fallback) without
# blocking. Prevents a cold-cache thundering herd during an on-sale.
_refresh_lock = threading.Lock()

# Module-level memo so a cache backend miss doesn't mean a refetch per
# request within one process.
_memo = {'ofac': None, 'ofac_at': 0.0, 'scam': None, 'scam_at': 0.0}


def _cache():
    from django.core.cache import cache
    return cache


def _fetch_ofac_union():
    import requests
    addresses = set()
    for ticker in _OFAC_EVM_TICKERS:
        resp = requests.get(_OFAC_URL.format(ticker=ticker), timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            addr = line.strip().lower()
            if addr.startswith('0x') and len(addr) == 42:
                addresses.add(addr)
    if not addresses:
        raise ValueError('OFAC fetch returned no addresses')
    return frozenset(addresses)


def _best_known_ofac():
    """Best non-fresh source, cheapest first: memoized set, last-good cache
    copy (stored without expiry), bundled snapshot."""
    if _memo['ofac'] is not None:
        return _memo['ofac']
    try:
        last_good = _cache().get('pretix_eth_ofac_addresses_lastgood')
        if last_good:
            return frozenset(last_good)
    except Exception:
        pass
    return _OFAC_FALLBACK


def get_ofac_addresses():
    """The current OFAC EVM address set. Never raises and never blocks more
    than one thread per process: falls back to the last-good copy, then to
    the bundled snapshot."""
    now = time.time()
    if _memo['ofac'] is not None and now - _memo['ofac_at'] < _CACHE_FRESH_SECONDS:
        return _memo['ofac']
    cached = None
    try:
        cached = _cache().get('pretix_eth_ofac_addresses')
    except Exception:
        pass
    if cached:
        _memo['ofac'], _memo['ofac_at'] = frozenset(cached), now
        return _memo['ofac']
    # Cold or expired: exactly one thread refreshes; the rest serve the best
    # known copy immediately.
    if not _refresh_lock.acquire(blocking=False):
        return _best_known_ofac()
    try:
        fresh = _fetch_ofac_union()
        try:
            _cache().set('pretix_eth_ofac_addresses', list(fresh), _CACHE_FRESH_SECONDS)
            _cache().set('pretix_eth_ofac_addresses_lastgood', list(fresh), None)
        except Exception:
            pass
        _memo['ofac'], _memo['ofac_at'] = fresh, now
        log.info('sanctions: refreshed OFAC EVM list (%d addresses)', len(fresh))
        return fresh
    except Exception as e:
        best = _best_known_ofac()
        log.warning('sanctions: OFAC list fetch failed (%s) — serving %d known addresses, retry in %ds',
                    e, len(best), _FAILURE_RETRY_SECONDS)
        # Memoize with a short freshness window so the next request after the
        # retry interval attempts a fresh fetch, not 24h later.
        _memo['ofac'], _memo['ofac_at'] = best, now - _CACHE_FRESH_SECONDS + _FAILURE_RETRY_SECONDS
        return best
    finally:
        _refresh_lock.release()


def is_sanctioned(address) -> bool:
    """True if `address` is on the OFAC SDN list. Empty/None → False."""
    if not address:
        return False
    return str(address).strip().lower() in get_ofac_addresses()


def is_scam_flagged(address) -> bool:
    """True if `address` is on the ScamSniffer community blacklist.
    Fails OPEN (False + warning log) if the list cannot be fetched — this
    list only gates refund warnings, never buyer checkout."""
    if not address:
        return False
    addr = str(address).strip().lower()
    now = time.time()
    if _memo['scam'] is not None and now - _memo['scam_at'] < _CACHE_FRESH_SECONDS:
        return addr in _memo['scam']
    cached = None
    try:
        cached = _cache().get('pretix_eth_scam_addresses')
    except Exception:
        pass
    if cached:
        _memo['scam'], _memo['scam_at'] = frozenset(cached), now
        return addr in _memo['scam']
    try:
        import requests
        resp = requests.get(_SCAM_URL, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        entries = frozenset(str(a).strip().lower() for a in resp.json() if str(a).startswith('0x'))
        try:
            _cache().set('pretix_eth_scam_addresses', list(entries), _CACHE_FRESH_SECONDS)
        except Exception:
            pass
        _memo['scam'], _memo['scam_at'] = entries, now
        log.info('sanctions: refreshed ScamSniffer list (%d addresses)', len(entries))
        return addr in entries
    except Exception as e:
        log.warning('sanctions: ScamSniffer fetch failed (%s) — scam screening fails open, retry in %ds',
                    e, _FAILURE_RETRY_SECONDS)
        # Short failure memo: one blip must not disable scam screening for 24h.
        _memo['scam'], _memo['scam_at'] = frozenset(), now - _CACHE_FRESH_SECONDS + _FAILURE_RETRY_SECONDS
        return False


# Bundled snapshot of the OFAC EVM union (2026-08-12, 104 addresses).
# Refresh with: devcon `pnpm ofac:scan` sources, or re-run the fetch above.
_OFAC_FALLBACK = frozenset([
    '0x0330070fd38ec3bb94f58fa55d40368271e9e54a',
    '0x038989cbb1710c72b9920dc4fa529158f463e72c',
    '0x04dba1194ee10112fe6c3207c0687def0e78bacf',
    '0x08723392ed15743cc38513c4925f5e6be5c17243',
    '0x08b2efdcdb8822efe5ad0eae55517cf5dc544251',
    '0x0931ca4d13bb4ba75d9b7132ab690265d749a5e7',
    '0x098b716b8aaf21512996dc57eb0615e2383e2f96',
    '0x0ee5067b06776a89ccc7dc8ee369984ad7db5e06',
    '0x12de548f79a50d2bd05481c8515c1ef5183666a9',
    '0x14779cec0b117d5194c750c55ea1f42086631964',
    '0x175d44451403edf28469df03a9280c1197adb92c',
    '0x1967d8af5bd86a497fb3dd7899a020e47560daaf',
    '0x1999ef52700c34de7ec2b68a28aafb37db0c5ade',
    '0x19aa5fe80d33a56d56c78e82ea5e50e5d80b4dff',
    '0x19f8f2b0915daa12a3f5c9cf01df9e24d53794f7',
    '0x1d19b52b54e7ef5ea1a4b40b616165e798eac9f8',
    '0x1da5821544e25c636c1417ba96ade4cf6d2f9b5a',
    '0x21b8d56bda776bbe68655a16895afd96f5534fed',
    '0x2711d73d559f62f4f855ee21f38378f528e07985',
    '0x2c7dcd774b33e10367f7d6385479e04f97d179dc',
    '0x2f389ce8bd8ff92de3402ffce4691d17fc4f6535',
    '0x308ed4b7b49797e1a98d3818bff6fe5385410370',
    '0x32da24ca413f3e7b53145d4737e172c3bdf81e3e',
    '0x35fb6f6db4fb05e6a4ce86f2c93691425626d4b1',
    '0x38735f03b30fbc022ddd06abed01f0ca823c6a94',
    '0x39d908dac893cbcb53cc86e0ecc369aa4def1a29',
    '0x3ad9db589d201a710ed237c829c7860ba86510fc',
    '0x3cbded43efdaf0fc77b9c55f6fc9988fcc9b757d',
    '0x3cffd56b47b7b41c56258d9c7731abadc360e073',
    '0x3e37627deaa754090fbfbb8bd226c1ce66d255e9',
    '0x43fa21d92141ba9db43052492e0deee5aa5f0a93',
    '0x48549a34ae37b12f6a30566245176994e17c6b4a',
    '0x4f428c11dc82388fa5136d636e613ad923eb700b',
    '0x4f47bc496083c727c5fbe3ce9cdf2b0f6496270c',
    '0x502371699497d08d5339c870851898d6d72521dd',
    '0x530a64c0ce595026a4a556b703644228179e2d57',
    '0x532b77b33a040587e9fd1800088225f99b8b0e8a',
    '0x53b6936513e738f44fb50d2b9476730c0ab3bfc1',
    '0x5512d943ed1f7c8a43f3435c85f7ab68b30121b0',
    '0x57ec89a0c056163a0314e413320f9b3abe761259',
    '0x5a14e72060c11313e38738009254a90968f58f51',
    '0x5a7a51bfb49f190e5a6060a5bc6052ac14a3b59f',
    '0x5d5b5dafecbf31bdb08bfd3edad4f2694372d0ef',
    '0x5f48c2a71b2cc96e3f0ccae4e39318ff0dc375b2',
    '0x67d40ee1a85bf4a4bb7ffae16de985e8427b6b45',
    '0x6b69e2a7545c166417a80c61a77562052bffa9c5',
    '0x6be0ae71e6c41f2f9d0d1a3b8d0f75e6f6a0b46e',
    '0x6f1ca141a28907f78ebaa64fb83a9088b02a8352',
    '0x72a5843cc08275c8171e582972aa4fda8c397b2a',
    '0x747afb5c7a7fc34b547cd0fdebf9b91759c5a52b',
    '0x76ea76ca4eb727f18956ab93445a94c5280412b9',
    '0x797d7ae72ebddcdea2a346c1834e04d1f8df102b',
    '0x7ced75026204ac29c34bea98905d4c949f27361e',
    '0x7db418b5d567a4e0e8c59ad71be1fce48f3e6107',
    '0x7f19720a857f834887fc9a7bc0a0fbe7fc7f8102',
    '0x7f367cc41522ce07553e823bf3be79a889debe1b',
    '0x7ff9cfad3877f21d41da833e2f775db0569ee3d9',
    '0x83e5bc4ffa856bb84bb88581f5dd62a433a25e0d',
    '0x8576acc5c05d6ce88f4e49bf65bdf0c62f91353c',
    '0x8d79c73daae8630c88de372ba8f57592fa987607',
    '0x8dce2aac0de82bdcaf6b4373b79f94331b8e4995',
    '0x901bb9583b24d97e995513c6778dc6888ab6870e',
    '0x931546d9e66836abf687d2bc64b30407bac8c568',
    '0x95584c303fcd48af5c6b9873015f2ad0ca84eae3',
    '0x961c5be54a2ffc17cf4cb021d863c42dacd47fc1',
    '0x97b1043abd9e6fc31681635166d430a458d14f9c',
    '0x983a81ca6fb1e441266d2fbcb7d8e530ac2e05a2',
    '0x9be599d7867f5e1a2d7ec6db9710df2b98a15573',
    '0x9c2bc757b66f24d60f016b6237f8cdd414a879fa',
    '0x9f4cda013e354b8fc285bf4b9a60460cee7f7ea9',
    '0xa0e1c89ef1a489c9c7de96311ed5ce5d32c20e4b',
    '0xa7e5d5a720f06526557c513402f2e6b5fa20b008',
    '0xac4cc4b68ea24bbfaac8fd127b67ed445accce22',
    '0xb338962b92cd818d6aef0a32a9ecd01212a71f33',
    '0xb637f84b66876ebf609c2a4208905f9ddac9d075',
    '0xb6f5ec1a0a9cd1526536d3f0426c429529471f40',
    '0xbb69e01921b17cd22080968bcc96ba6115da6062',
    '0xc103b7dc095c904b92081eef0c1640081ec01c10',
    '0xc2a3829f459b3edd87791c74cd45402ba0a20be3',
    '0xc455f7fd3e0e12afd51fba5c106909934d8a0e4a',
    '0xcb74874f1e06fcf80a306e06e5379a44b488ba2d',
    '0xd04e33461fea8302c5e1e13895b60cee8aefda7f',
    '0xd0975b32cea532eadddfc9c60481976e39db3472',
    '0xd5ed34b52ac4ab84d8fa8a231a3218bbf01ed510',
    '0xd8500c631dc32fa18645b7436344a99e4825e10e',
    '0xd882cfc20f52f2599d84b8e8d58c7fb62cfe344b',
    '0xdb2720ebad55399117ddb4c4a4afd9a4ccada8fe',
    '0xdcbeffbecce100cce9e4b153c4e15cb885643193',
    '0xe05f529f5284d75624eba386cb716928c3b54a2a',
    '0xe1d865c3d669dcc8c57c8d023140cb204e672ee4',
    '0xe1e4c5e5ed8f03ae61b581e2def126025f2b9401',
    '0xe3d35f68383732649669aa990832e017340dbca5',
    '0xe7aa314c77f4233c18c6cc84384a9247c0cf367b',
    '0xe950dc316b836e4eefb8308bf32bf7c72a1358ff',
    '0xed6e0a7e4ac94d976eebfb82ccf777a3c6bad921',
    '0xefe301d259f525ca1ba74a7977b80d5b060b3cca',
    '0xf2235d55b2950a0b1317469d72d07ae65b2e27cb',
    '0xf3701f445b6bdafedbca97d1e477357839e4120d',
    '0xf4377eda661e04b6dda78969796ed31658d602d4',
    '0xf7b31119c2682c88d88d455dbb9d5932c65cf1be',
    '0xfac583c0cf07ea434052c49115a4682172ab6b4f',
    '0xfb3eff152ea55d1bfa04dbdd509a80fd7b72cdeb',
    '0xfda1ec4a6178d4916b001a065422d31ebe5f62ff',
    '0xfec8a60023265364d066a1212fde3930f6ae8da7',
])
