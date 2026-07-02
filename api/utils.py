from decimal import Decimal
from django.db.models import Sum
from .models import Transaction, UserProfile

POINTS = 12


def _pad_series(values, points=POINTS):
    values = [float(v) for v in values]
    if len(values) >= points:
        step = len(values) / points
        return [values[int(i * step)] for i in range(points)]
    return [0.0] * (points - len(values)) + values


def build_stats_trends(user):
    trends = {
        'balance': [0.0] * POINTS,
        'deposit': [0.0] * POINTS,
        'withdraw': [0.0] * POINTS,
        'profit': [0.0] * POINTS,
    }

    deposit_amounts = list(
        Transaction.objects.filter(user=user, type='deposit')
        .order_by('created_at')
        .values_list('amount', flat=True)
    )
    withdraw_amounts = list(
        Transaction.objects.filter(user=user, type='withdraw')
        .order_by('created_at')
        .values_list('amount', flat=True)
    )
    profit_amounts = list(
        Transaction.objects.filter(user=user, type__in=['profit', 'stack'])
        .order_by('created_at')
        .values_list('amount', flat=True)
    )

    trends['deposit'] = _pad_series(deposit_amounts)
    trends['withdraw'] = _pad_series(withdraw_amounts)
    trends['profit'] = _pad_series(profit_amounts)

    cumulative = []
    running = Decimal('0')
    for tx in Transaction.objects.filter(user=user).order_by('created_at'):
        if tx.type in ('deposit', 'profit', 'stack', 'referral'):
            running += tx.amount
        elif tx.type == 'withdraw':
            running -= tx.amount
        cumulative.append(float(running))

    trends['balance'] = _pad_series(cumulative) if cumulative else [0.0] * POINTS
    return trends


def build_referral_levels(profile):
    direct_refs = UserProfile.objects.filter(referred_by=profile)
    level2_profiles = UserProfile.objects.filter(referred_by__in=direct_refs)

    return [
        {
            'level': 1,
            'members': direct_refs.count(),
            'earnings': float(
                Transaction.objects.filter(
                    user=profile.user, type='referral', description__icontains='Level 1'
                ).aggregate(Sum('amount'))['amount__sum'] or 0
            ),
        },
        {
            'level': 2,
            'members': level2_profiles.count(),
            'earnings': float(
                Transaction.objects.filter(
                    user=profile.user, type='referral', description__icontains='Level 2'
                ).aggregate(Sum('amount'))['amount__sum'] or 0
            ),
        },
        {
            'level': 3,
            'members': UserProfile.objects.filter(referred_by__in=level2_profiles).count(),
            'earnings': float(
                Transaction.objects.filter(
                    user=profile.user, type='referral', description__icontains='Level 3'
                ).aggregate(Sum('amount'))['amount__sum'] or 0
            ),
        },
    ]
