# Generated by Django 3.2.16 on 2023-06-27 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pretix_eth', '0008_signedmessage_safe_app_transaction_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signedmessage',
            name='safe_app_transaction_url',
            field=models.TextField(null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='signedmessage',
            name='transaction_hash',
            field=models.CharField(max_length=66, null=True, unique=True),
        ),
    ]
