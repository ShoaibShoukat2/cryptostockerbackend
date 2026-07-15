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


class SiteConfig(models.Model):
    """Singleton platform settings — editable by admin/operator."""
    bep20_address = models.CharField(max_length=255, blank=True, default='')
    trc20_address = models.CharField(max_length=255, blank=True, default='')
    telegram_link = models.CharField(max_length=255, blank=True, default='https://t.me/cryptostacker')
    support_heading = models.CharField(max_length=100, blank=True, default='Telegram Support')
    support_subtitle = models.CharField(
        max_length=255, blank=True, default='Our team is available 24/7 on Telegram',
    )
    min_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('50.00'))
    min_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('20.00'))
    referral_commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.12'))
    daily_bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('15.00'))
    daily_bonus_referrals = models.IntegerField(default=3)
    investment_lock_days = models.IntegerField(default=30)
    promotion_bonus_subtitle = models.CharField(
        max_length=255, blank=True, default='Upload videos and earn extra rewards',
    )
    promotion_bonus_note = models.TextField(
        blank=True,
        default='Contact support on Telegram to claim your promotion bonus rewards.',
    )
    promotion_tier1_detail = models.CharField(
        max_length=255, blank=True, default='Upload 1 video daily for 7 days',
    )
    promotion_tier1_reward = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('5.00'),
    )
    promotion_tier2_detail = models.CharField(
        max_length=255, blank=True, default='5k views on a video',
    )
    promotion_tier2_reward = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('10.00'),
    )
    promotion_tier3_detail = models.CharField(
        max_length=255, blank=True, default='10k views on a video',
    )
    promotion_tier3_reward = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('30.00'),
    )
    tier1_profit_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0140'))
    tier2_profit_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0200'))
    tier3_profit_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0250'))
    tier4_profit_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0300'))
    about_text = models.TextField(blank=True, default=(
        'Crypto Stacker is a professional crypto trading platform. '
        'We invest your deposits in crypto trading markets and share daily profits with you. '
        'Stack your balance every 24 hours to earn tier-based returns on your total balance.'
    ))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Configuration'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Site Configuration'


class UserProfile(models.Model):
    VIP_LEVELS = [(i, f'VIP {i}') for i in range(1, 6)]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    plain_password = models.CharField(max_length=128, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    referral_code = models.CharField(max_length=10, unique=True, default=generate_referral_code)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals',
    )
    vip_level = models.IntegerField(choices=VIP_LEVELS, default=1)
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    locked_investment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_referral_bonus = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    extra_bonus_awarded = models.BooleanField(default=False)
    extra_bonus_qualified_count = models.IntegerField(default=0)
    referral_deposit_counted = models.BooleanField(default=False)
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
        min_dep = SiteConfig.load().min_deposit or Decimal('50.00')
        return self.referrals.filter(total_deposit__gte=min_dep).count()

    @property
    def active_referrals(self):
        min_dep = SiteConfig.load().min_deposit or Decimal('50.00')
        return self.referrals.filter(
            total_deposit__gte=min_dep,
            user__is_active=True,
        ).count()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class InvestmentLock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investment_locks')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    unlock_at = models.DateTimeField()
    released = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['unlock_at']


class DailyReferralTracker(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_referral_trackers')
    date = models.DateField()
    referral_count = models.IntegerField(default=0)
    bonus_awarded = models.BooleanField(default=False)

    class Meta:
        unique_together = ['user', 'date']


class Deposit(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    NETWORK_CHOICES = [
        ('BEP20', 'BEP20'),
        ('TRC20', 'TRC20'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    network = models.CharField(max_length=10, choices=NETWORK_CHOICES, default='BEP20')
    screenshot = models.ImageField(upload_to='deposits/', blank=True, null=True)
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
    NETWORK_CHOICES = [
        ('BEP20', 'BEP20'),
        ('TRC20', 'TRC20'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    network = models.CharField(max_length=10, choices=NETWORK_CHOICES, default='BEP20')
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
    profit_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.014'))
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
    TYPE_CHOICES = [
        ('general', 'General'),
        ('stack', 'Stack Result'),
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('referral', 'Referral'),
        ('bonus', 'Bonus'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    extra_data = models.JSONField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ContactMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contact_messages')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.subject}'
