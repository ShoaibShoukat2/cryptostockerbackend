from django.db import migrations, models


def set_lock_days_to_30(apps, schema_editor):
    SiteConfig = apps.get_model('api', 'SiteConfig')
    SiteConfig.objects.filter(pk=1, investment_lock_days=7).update(investment_lock_days=30)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_siteconfig_min_deposit_50'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfig',
            name='investment_lock_days',
            field=models.IntegerField(default=30),
        ),
        migrations.RunPython(set_lock_days_to_30, migrations.RunPython.noop),
    ]
