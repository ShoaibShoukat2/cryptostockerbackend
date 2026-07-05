from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_userprofile_plain_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_bonus_note',
            field=models.TextField(
                blank=True,
                default='Contact support on Telegram to claim your promotion bonus rewards.',
            ),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_bonus_subtitle',
            field=models.CharField(
                blank=True,
                default='Upload videos and earn extra rewards',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_tier1_detail',
            field=models.CharField(
                blank=True,
                default='Upload 1 video daily for 7 days',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_tier1_reward',
            field=models.DecimalField(decimal_places=2, default=Decimal('5.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_tier2_detail',
            field=models.CharField(
                blank=True,
                default='5k views on a video',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_tier2_reward',
            field=models.DecimalField(decimal_places=2, default=Decimal('10.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_tier3_detail',
            field=models.CharField(
                blank=True,
                default='10k views on a video',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='promotion_tier3_reward',
            field=models.DecimalField(decimal_places=2, default=Decimal('30.00'), max_digits=12),
        ),
    ]
