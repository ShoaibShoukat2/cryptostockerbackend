from decimal import Decimal

from django.db import migrations, models


def set_min_deposit_to_50(apps, schema_editor):
    SiteConfig = apps.get_model('api', 'SiteConfig')
    for config in SiteConfig.objects.filter(min_deposit=Decimal('100.00')):
        config.min_deposit = Decimal('50.00')
        config.save(update_fields=['min_deposit'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_siteconfig_tier_profit_rates'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfig',
            name='min_deposit',
            field=models.DecimalField(decimal_places=2, default=Decimal('50.00'), max_digits=12),
        ),
        migrations.RunPython(set_min_deposit_to_50, migrations.RunPython.noop),
    ]
