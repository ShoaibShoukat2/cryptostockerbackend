"""Core business rules: referral tiers, stack profit, locks, extra bonus."""
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import UserProfile, InvestmentLock, Transaction, SiteConfig, Notification

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


def _format_profit_percent(rate):
    pct = float(rate) * 100
    if pct == int(pct):
        return f'{int(pct)}%'
    return f'{pct:g}%'


def get_referral_tier_requirements():
    config = SiteConfig.load()
    configured_rates = [
        config.tier1_profit_rate,
        config.tier2_profit_rate,
        config.tier3_profit_rate,
        config.tier4_profit_rate,
    ]
    tiers = []
    for index, base in enumerate(REFERRAL_TIER_REQUIREMENTS):
        configured = configured_rates[index] if index < len(configured_rates) else None
        profit_rate = Decimal(str(configured or base['profit_rate']))
        tiers.append({
            **base,
            'profit_rate': profit_rate,
            'profit_percent': _format_profit_percent(profit_rate),
        })
    return tiers


def get_min_deposit_threshold():
    config = SiteConfig.load()
    return config.min_deposit or Decimal(str(getattr(settings, 'MIN_DEPOSIT', 50)))


def count_direct_members(profile):
    min_dep = get_min_deposit_threshold()
    return UserProfile.objects.filter(
        referred_by=profile,
        total_deposit__gte=min_dep,
    ).count()


def count_qualified_bonus_referrals(profile):
    """Direct referrals who completed minimum deposit — used for extra bonus progress."""
    return count_direct_members(profile)


def count_indirect_members(profile):
    min_dep = get_min_deposit_threshold()
    direct_ids = UserProfile.objects.filter(referred_by=profile).values_list('pk', flat=True)
    return UserProfile.objects.filter(
        referred_by_id__in=direct_ids,
        total_deposit__gte=min_dep,
    ).count()


def get_user_tier(profile):
    direct = count_direct_members(profile)
    indirect = count_indirect_members(profile)
    deposit = profile.total_deposit
    tiers = get_referral_tier_requirements()
    matched = tiers[0]
    for tier in tiers:
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


def track_referral_deposit(referrer_profile):
    """Award lifetime extra bonus when enough referrals deposit the minimum amount."""
    if referrer_profile.extra_bonus_awarded:
        return Decimal('0')

    config = SiteConfig.load()
    threshold = int(config.daily_bonus_referrals or getattr(settings, 'DAILY_BONUS_REFERRALS', 3))
    bonus_amount = config.daily_bonus_amount or Decimal(str(getattr(settings, 'DAILY_BONUS_AMOUNT', 15)))
    min_dep = get_min_deposit_threshold()
    count = count_qualified_bonus_referrals(referrer_profile)

    referrer_profile.extra_bonus_qualified_count = count
    update_fields = ['extra_bonus_qualified_count']

    if count >= threshold:
        referrer_profile.extra_bonus_awarded = True
        referrer_profile.available_balance += bonus_amount
        referrer_profile.total_balance += bonus_amount
        referrer_profile.total_referral_bonus += bonus_amount
        update_fields.extend([
            'extra_bonus_awarded', 'available_balance', 'total_balance', 'total_referral_bonus',
        ])
        referrer_profile.save(update_fields=update_fields)
        Transaction.objects.create(
            user=referrer_profile.user,
            type='referral',
            amount=bonus_amount,
            description=(
                f'Extra bonus: {threshold} referrals with ${min_dep:.0f}+ deposit (lifetime)'
            ),
        )
        Notification.objects.create(
            user=referrer_profile.user,
            title='Extra Bonus Earned',
            message=(
                f'Congratulations! You earned ${bonus_amount:.2f} extra bonus for '
                f'{threshold} referrals who deposited ${min_dep:.0f} or more.'
            ),
            notification_type='bonus',
        )
        return bonus_amount

    referrer_profile.save(update_fields=update_fields)
    return Decimal('0')


def process_referral_deposit_qualification(deposit_user_profile):
    """Mark a referred user as a qualifying team member after they reach min deposit."""
    if deposit_user_profile.referral_deposit_counted:
        return Decimal('0')

    min_dep = get_min_deposit_threshold()
    if deposit_user_profile.total_deposit < min_dep:
        return Decimal('0')

    deposit_user_profile.referral_deposit_counted = True
    deposit_user_profile.save(update_fields=['referral_deposit_counted'])

    if deposit_user_profile.referred_by:
        return track_referral_deposit(deposit_user_profile.referred_by)
    return Decimal('0')


def get_extra_bonus_status(profile):
    config = SiteConfig.load()
    threshold = int(config.daily_bonus_referrals or getattr(settings, 'DAILY_BONUS_REFERRALS', 3))
    bonus_amount = float(config.daily_bonus_amount or getattr(settings, 'DAILY_BONUS_AMOUNT', 15))
    min_deposit = float(get_min_deposit_threshold())
    count = count_qualified_bonus_referrals(profile)
    awarded = profile.extra_bonus_awarded
    return {
        'referrals_today': count,
        'qualified_referrals': count,
        'required': threshold,
        'bonus_amount': bonus_amount,
        'min_deposit_required': min_deposit,
        'awarded_today': awarded,
        'awarded_lifetime': awarded,
        'remaining': max(0, threshold - count) if not awarded else 0,
    }


get_daily_bonus_status = get_extra_bonus_status


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
    for tier in get_referral_tier_requirements():
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
