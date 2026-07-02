import uuid
import string
import random
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


class UserProfile(models.Model):
    VIP_LEVELS = [(i, f'VIP {i}') for i in range(1, 6)]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    referral_code = models.CharField(max_length=10, unique=True, default=generate_referral_code)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals'
    )
    vip_level = models.IntegerField(choices=VIP_LEVELS, default=1)
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_referral_bonus = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_stack_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - VIP{self.vip_level}'

    @property
    def can_stack(self):
        if not self.last_stack_at:
            return True
        return timezone.now() - self.last_stack_at >= timezone.timedelta(hours=24)

    @property
    def next_stack_in_seconds(self):
        if not self.last_stack_at:
            return 0
        elapsed = timezone.now() - self.last_stack_at
        remaining = timezone.timedelta(hours=24) - elapsed
        return max(0, int(remaining.total_seconds()))

    @property
    def total_referrals(self):
        return self.referrals.count()

    @property
    def active_referrals(self):
        return self.referrals.filter(user__is_active=True).count()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class Deposit(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    wallet_address = models.CharField(max_length=255, blank=True)
    transaction_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class StackLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stack_logs')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    profit_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('stack', 'Stack'),
        ('profit', 'Profit'),
        ('referral', 'Referral Bonus'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
