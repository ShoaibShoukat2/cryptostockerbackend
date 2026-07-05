from decimal import Decimal

from django.db import migrations, models


def backfill_referral_deposit_counts(apps, schema_editor):
    UserProfile = apps.get_model('api', 'UserProfile')
    SiteConfig = apps.get_model('api', 'SiteConfig')
    config = SiteConfig.objects.filter(pk=1).first()
    min_dep = config.min_deposit if config else Decimal('100.00')

    qualifying = UserProfile.objects.filter(
        total_deposit__gte=min_dep,
        referral_deposit_counted=False,
        referred_by__isnull=False,
    ).select_related('referred_by')

    for profile in qualifying:
        profile.referral_deposit_counted = True
        profile.save(update_fields=['referral_deposit_counted'])
        referrer = profile.referred_by
        if referrer.extra_bonus_awarded:
            continue
        referrer.extra_bonus_qualified_count += 1
        threshold = config.daily_bonus_referrals if config else 3
        bonus_amount = config.daily_bonus_amount if config else Decimal('15.00')
        if referrer.extra_bonus_qualified_count >= threshold:
            referrer.extra_bonus_awarded = True
            referrer.available_balance += bonus_amount
            referrer.total_balance += bonus_amount
            referrer.total_referral_bonus += bonus_amount
        referrer.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_contactmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='extra_bonus_awarded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='extra_bonus_qualified_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='referral_deposit_counted',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_referral_deposit_counts, migrations.RunPython.noop),
    ]
