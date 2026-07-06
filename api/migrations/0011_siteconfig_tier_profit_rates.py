from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_withdrawal_network'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='tier1_profit_rate',
            field=models.DecimalField(decimal_places=4, default=Decimal('0.0140'), max_digits=6),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='tier2_profit_rate',
            field=models.DecimalField(decimal_places=4, default=Decimal('0.0200'), max_digits=6),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='tier3_profit_rate',
            field=models.DecimalField(decimal_places=4, default=Decimal('0.0250'), max_digits=6),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='tier4_profit_rate',
            field=models.DecimalField(decimal_places=4, default=Decimal('0.0300'), max_digits=6),
        ),
    ]
