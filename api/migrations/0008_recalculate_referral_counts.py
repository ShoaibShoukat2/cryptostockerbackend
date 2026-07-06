from decimal import Decimal

from django.db import migrations


def recalculate_referral_counts(apps, schema_editor):
    UserProfile = apps.get_model('api', 'UserProfile')
    SiteConfig = apps.get_model('api', 'SiteConfig')
    config = SiteConfig.objects.filter(pk=1).first()
    min_dep = config.min_deposit if config else Decimal('100.00')

    UserProfile.objects.filter(total_deposit__lt=min_dep).update(referral_deposit_counted=False)

    for referrer in UserProfile.objects.all():
        qualified_count = UserProfile.objects.filter(
            referred_by=referrer,
            total_deposit__gte=min_dep,
        ).count()
        if referrer.extra_bonus_qualified_count != qualified_count:
            referrer.extra_bonus_qualified_count = qualified_count
            referrer.save(update_fields=['extra_bonus_qualified_count'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_userprofile_extra_bonus_fields'),
    ]

    operations = [
        migrations.RunPython(recalculate_referral_counts, migrations.RunPython.noop),
    ]
