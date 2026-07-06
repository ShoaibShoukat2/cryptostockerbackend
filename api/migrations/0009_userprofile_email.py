from django.db import migrations, models


def copy_user_emails_to_profile(apps, schema_editor):
    UserProfile = apps.get_model('api', 'UserProfile')
    for profile in UserProfile.objects.select_related('user').iterator():
        user_email = profile.user.email or ''
        if user_email and not profile.email:
            profile.email = user_email
            profile.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_recalculate_referral_counts'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='email',
            field=models.EmailField(blank=True, default=''),
        ),
        migrations.RunPython(copy_user_emails_to_profile, migrations.RunPython.noop),
    ]
