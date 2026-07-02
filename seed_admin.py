import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cryptostacker.settings')
django.setup()

from django.contrib.auth.models import User
from api.models import Deposit, Withdrawal, StackLog, Transaction, Notification


def run():
    """Remove demo/sample users and keep only admin accounts."""
    demo_users = User.objects.filter(is_staff=False)
    count = demo_users.count()
    if count:
        demo_users.delete()
        print(f'Removed {count} non-admin user(s) and all related data.')

    admin_exists = User.objects.filter(is_staff=True).exists()
    if not admin_exists:
        User.objects.create_superuser('admin', 'admin@cryptostacker.com', 'admin123')
        print('Admin created: admin / admin123')
    else:
        print('Admin account already exists.')

    print('Database is clean. Register new users from the app.')


if __name__ == '__main__':
    run()
