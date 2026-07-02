import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cryptostacker.settings')
django.setup()

from django.contrib.auth.models import User
from api.models import Deposit, Withdrawal, StackLog, Transaction, Notification


def run():
    """Remove all sample users and transactional data. Keeps admin accounts only."""
    removed = User.objects.filter(is_staff=False).delete()
    print(f'Removed non-admin users and related records: {removed}')

    admin_exists = User.objects.filter(is_staff=True).exists()
    if not admin_exists:
        User.objects.create_superuser('admin', 'admin@cryptostacker.com', 'admin123')
        print('Admin created: admin / admin123')
    else:
        print('Admin account kept.')

    print('Database clean. Register new users from the app — all balances start at $0.')


if __name__ == '__main__':
    run()
