from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_siteconfig_promotion_bonus'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='support_heading',
            field=models.CharField(blank=True, default='Telegram Support', max_length=100),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='support_subtitle',
            field=models.CharField(
                blank=True,
                default='Our team is available 24/7 on Telegram',
                max_length=255,
            ),
        ),
    ]
