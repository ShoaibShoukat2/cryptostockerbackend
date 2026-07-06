from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_userprofile_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawal',
            name='network',
            field=models.CharField(
                choices=[('BEP20', 'BEP20'), ('TRC20', 'TRC20')],
                default='BEP20',
                max_length=10,
            ),
        ),
    ]
