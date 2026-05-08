"""Canonicalise existing tx_hash rows to lowercase before V45's stricter
exact-match dedup ships.

Both `WCPaymentAttempt` and `X402CompletedOrder` hold tx hashes; pre-fix
code preserved caller casing on insert, so older rows may be mixed-case.
After this migration all rows are lowercase and the V45 fix's exact-match
pre-check stays consistent with on-disk state.

# Dirty-DB handling

Some long-running deployments may have accumulated rows that collide on
lowercase (e.g. an `0xABC…` followed by an `0xabc…` from a separate
flow that didn't dedup pre-fix). A naive `UPDATE … SET tx_hash = LOWER(…)`
would violate the unique constraint and abort the migration mid-flight,
leaving the table in a half-canonicalised state.

Strategy:

  1. Pre-flight collision detection — for each model, group rows by
     `LOWER(tx_hash)` and find groups with count > 1.
  2. Within each colliding group, keep the **earliest** row (smallest pk),
     pre-set its tx_hash to the canonical lowercase form, and delete the
     others. We keep the earliest because it's most likely the row tied
     to the order that actually settled; later rows are usually retries
     or duplicates from a stuck flow.
  3. Then bulk-lowercase the rest of the rows (no more collisions
     possible).

If you'd rather audit/merge collisions manually before running this
migration, set `PRETIX_ETH_SKIP_TX_HASH_DEDUP=1` in the environment;
the migration will then fail fast with a list of colliding hashes
instead of auto-deleting duplicates.
"""
import logging
import os
from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower


log = logging.getLogger('pretix_eth.migrations.0014')


def _resolve_collisions(model, *, dry_run):
    collisions = (
        model.objects
        .annotate(lower_hash=Lower('tx_hash'))
        .values('lower_hash')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    colliding_hashes = [c['lower_hash'] for c in collisions]
    if not colliding_hashes:
        return 0

    if dry_run:
        msg = (
            f'{model._meta.label}: {len(colliding_hashes)} tx_hash collision(s) '
            f'after lowercasing — refusing auto-merge because '
            f'PRETIX_ETH_SKIP_TX_HASH_DEDUP=1 is set. Hashes: {colliding_hashes!r}'
        )
        raise RuntimeError(msg)

    deleted_total = 0
    for lower_hash in colliding_hashes:
        rows = list(
            model.objects.filter(tx_hash__iexact=lower_hash).order_by('pk')
        )
        if not rows:
            continue
        canonical = rows[0]
        # Pre-set the canonical row to its lowercase form so the later
        # bulk update sees no further work for this hash.
        if canonical.tx_hash != lower_hash:
            canonical.tx_hash = lower_hash
            canonical.save(update_fields=['tx_hash'])
        log.warning(
            '0014_lowercase_tx_hashes: %s — keeping pk=%s, deleting %d duplicate(s) for hash %s',
            model._meta.label, canonical.pk, len(rows) - 1, lower_hash,
        )
        for dup in rows[1:]:
            dup.delete()
            deleted_total += 1
    return deleted_total


def forwards(apps, schema_editor):
    dry_run = os.environ.get('PRETIX_ETH_SKIP_TX_HASH_DEDUP') == '1'
    WCPaymentAttempt = apps.get_model('pretix_eth', 'WCPaymentAttempt')
    X402CompletedOrder = apps.get_model('pretix_eth', 'X402CompletedOrder')

    for model in (WCPaymentAttempt, X402CompletedOrder):
        # Step 1+2: dedup colliding rows so the bulk update doesn't trip
        # the unique constraint.
        deleted = _resolve_collisions(model, dry_run=dry_run)
        if deleted:
            log.warning(
                '0014_lowercase_tx_hashes: %s — deleted %d duplicate row(s)',
                model._meta.label, deleted,
            )

        # Step 3: bulk lowercase the remaining (non-colliding) rows. We
        # iterate-and-save instead of `update(tx_hash=Lower('tx_hash'))`
        # because we already canonicalised collision winners above; this
        # second pass mostly catches case-different but otherwise unique
        # rows (e.g. a single `0xAB…` with no `0xab…` sibling).
        for row in model.objects.all().iterator():
            lowered = (row.tx_hash or '').lower()
            if lowered != row.tx_hash:
                row.tx_hash = lowered
                row.save(update_fields=['tx_hash'])


def backwards(apps, schema_editor):
    # No-op — lowercasing is information-preserving for hex hashes, and the
    # delete step in `forwards` is irreversible (we don't have the original
    # rows to restore). If a backout is required, restore from a pre-migration
    # database snapshot.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pretix_eth', '0013_x402verifyattempt'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
