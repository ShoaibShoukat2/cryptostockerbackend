"""Core business rules: referral tiers, stack profit, locks, daily bonus."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from .models import UserProfile, InvestmentLock, DailyReferralTracker, Transaction

REFERRAL_TIER_REQUIREMENTS = [
    {
        'level': 1,
        'direct': 0,
        'indirect': 0,
        'total_deposit': Decimal('100'),
        'profit_rate': Decimal('0.014'),
        'profit_percent': '1.4%',
    },
    {
        'level': 2,
        'direct': 8,
        'indirect': 2,
        'total_deposit': Decimal('1000'),
        'profit_rate': Decimal('0.02'),
        'profit_percent': '2%',
    },
    {
        'level': 3,
        'direct': 22,
        'indirect': 8,
        'total_deposit': Decimal('3000'),
        'profit_rate': Decimal('0.025'),
        'profit_percent': '2.5%',
    },
    {
        'level': 4,
        'direct': 38,
        'indirect': 12,
        'total_deposit': Decimal('5000'),
        'profit_rate': Decimal('0.03'),
        'profit_percent': '3%',
    },
]


def count_direct_members(profile):
    return UserProfile.objects.filter(referred_by=profile).count()


def count_indirect_members(profile):
    direct = UserProfile.objects.filter(referred_by=profile)
    return UserProfile.objects.filter(referred_by__in=direct).count()


def get_user_tier(profile):
    direct = count_direct_members(profile)
    indirect = count_indirect_members(profile)
    deposit = profile.total_deposit
    matched = REFERRAL_TIER_REQUIREMENTS[0]
    for tier in REFERRAL_TIER_REQUIREMENTS:
        if (
            direct >= tier['direct']
            and indirect >= tier['indirect']
            and deposit >= tier['total_deposit']
        ):
            matched = tier
    return matched


def get_profit_rate(profile):
    return get_user_tier(profile)['profit_rate']


def release_expired_locks(profile):
    now = timezone.now()
    locks = InvestmentLock.objects.filter(
        user=profile.user, released=False, unlock_at__lte=now,
    )
    released_total = Decimal('0')
    for lock in locks:
        released_total += lock.amount
        lock.released = True
        lock.save(update_fields=['released'])
    if released_total > 0:
        profile.locked_investment = max(
            Decimal('0'), profile.locked_investment - released_total,
        )
        profile.save(update_fields=['locked_investment'])
    return released_total


def get_withdrawable_balance(profile):
    release_expired_locks(profile)
    return max(Decimal('0'), profile.available_balance - profile.locked_investment)


def create_investment_lock(user, amount):
    days = int(getattr(settings, 'INVESTMENT_LOCK_DAYS', 7))
    unlock_at = timezone.now() + timezone.timedelta(days=days)
    InvestmentLock.objects.create(user=user, amount=amount, unlock_at=unlock_at)
    profile = user.profile
    profile.locked_investment += amount
    profile.save(update_fields=['locked_investment'])


def track_referral_signup(referrer_profile, new_username):
    """Count daily referrals and award bonus when threshold reached in one day."""
    today = timezone.now().date()
    tracker, _ = DailyReferralTracker.objects.get_or_create(
        user=referrer_profile.user,
        date=today,
        defaults={'referral_count': 0, 'bonus_awarded': False},
    )
    tracker.referral_count += 1
    tracker.save(update_fields=['referral_count'])

    threshold = int(getattr(settings, 'DAILY_BONUS_REFERRALS', 3))
    bonus_amount = Decimal(str(getattr(settings, 'DAILY_BONUS_AMOUNT', 15)))

    if tracker.referral_count >= threshold and not tracker.bonus_awarded:
        tracker.bonus_awarded = True
        tracker.save(update_fields=['bonus_awarded'])
        referrer_profile.available_balance += bonus_amount
        referrer_profile.total_balance += bonus_amount
        referrer_profile.total_referral_bonus += bonus_amount
        referrer_profile.save()
        Transaction.objects.create(
            user=referrer_profile.user,
            type='referral',
            amount=bonus_amount,
            description=f'Daily bonus: {threshold} referrals in one day',
        )
        return bonus_amount
    return Decimal('0')


def get_daily_bonus_status(profile):
    today = timezone.now().date()
    tracker = DailyReferralTracker.objects.filter(user=profile.user, date=today).first()
    threshold = int(getattr(settings, 'DAILY_BONUS_REFERRALS', 3))
    bonus_amount = float(getattr(settings, 'DAILY_BONUS_AMOUNT', 15))
    count = tracker.referral_count if tracker else 0
    awarded = tracker.bonus_awarded if tracker else False
    return {
        'referrals_today': count,
        'required': threshold,
        'bonus_amount': bonus_amount,
        'awarded_today': awarded,
        'remaining': max(0, threshold - count),
    }


def build_tier_levels(profile):
    direct = count_direct_members(profile)
    indirect = count_indirect_members(profile)
    current = get_user_tier(profile)
    referral_earnings = float(
        Transaction.objects.filter(user=profile.user, type='referral').aggregate(
            total=Sum('amount'),
        )['total'] or 0,
    )
    levels = []
    for tier in REFERRAL_TIER_REQUIREMENTS:
        levels.append({
            'level': tier['level'],
            'direct_required': tier['direct'],
            'indirect_required': tier['indirect'],
            'deposit_required': float(tier['total_deposit']),
            'profit_percent': tier['profit_percent'],
            'profit_rate': float(tier['profit_rate']),
            'direct_members': direct,
            'indirect_members': indirect,
            'user_deposit': float(profile.total_deposit),
            'unlocked': tier['level'] <= current['level'],
            'current': tier['level'] == current['level'],
            'earnings': referral_earnings if tier['level'] == 1 else 0,
        })
    return levels
