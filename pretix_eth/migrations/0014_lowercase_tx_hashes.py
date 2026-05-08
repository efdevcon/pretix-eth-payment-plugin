"""Canonicalise existing tx_hash rows to lowercase before V45's stricter
exact-match dedup ships. Both WCPaymentAttempt and X402CompletedOrder hold
tx hashes; pre-fix code preserved caller casing on insert, so older rows
may be mixed-case. After this migration all rows are lowercase and the
V45 fix's exact-match pre-check stays consistent with on-disk state.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    WCPaymentAttempt = apps.get_model('pretix_eth', 'WCPaymentAttempt')
    X402CompletedOrder = apps.get_model('pretix_eth', 'X402CompletedOrder')
    for model in (WCPaymentAttempt, X402CompletedOrder):
        for row in model.objects.all().iterator():
            lowered = (row.tx_hash or '').lower()
            if lowered != row.tx_hash:
                row.tx_hash = lowered
                row.save(update_fields=['tx_hash'])


def backwards(apps, schema_editor):
    # No-op — lowercasing is information-preserving for hex hashes.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pretix_eth', '0013_x402verifyattempt'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
