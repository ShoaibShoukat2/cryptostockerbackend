from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_siteconfig_deposit_network_deposit_screenshot_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='plain_password',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
    ]
