from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import generics, status, views, parsers
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    UserProfile, Deposit, Withdrawal, StackLog, Transaction,
    Notification, SiteConfig,
)
from .market_service import get_btc_market, get_btc_price
from .utils import build_stats_trends, build_referral_levels, get_today_stack_profit
from .business_logic import (
    get_profit_rate, get_user_tier, get_withdrawable_balance,
    create_investment_lock, get_daily_bonus_status, release_expired_locks,
)
from .serializers import (
    RegisterSerializer, UserProfileSerializer, DepositSerializer,
    WithdrawalSerializer, StackLogSerializer, TransactionSerializer,
    NotificationSerializer, AdminUserSerializer, AdminDepositSerializer,
    AdminWithdrawalSerializer, AdminTransactionSerializer,
    AdminUserUpdateSerializer, AdminNotifySerializer, SiteConfigSerializer,
)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response({
            'user': UserProfileSerializer(user.profile).data,
            'tokens': tokens,
            'message': 'Registration successful!',
        }, status=status.HTTP_201_CREATED)


class LoginView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''

        if not username or not password:
            return Response(
                {'detail': 'Username and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.select_related('profile').get(username=username)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        stored_password = user.profile.plain_password
        if stored_password:
            authenticated = password == stored_password
        else:
            authenticated = user.check_password(password)

        if not authenticated:
            return Response(
                {'detail': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {'detail': 'User account is disabled.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(get_tokens_for_user(user))


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user.profile


class SiteConfigView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        config = SiteConfig.load()
        return Response(SiteConfigSerializer(config).data)


class DashboardView(views.APIView):
    def get(self, request):
        profile = request.user.profile
        release_expired_locks(profile)
        profile.refresh_from_db()

        pending_deposits = Deposit.objects.filter(user=request.user, status='pending')
        pending_withdrawals = Withdrawal.objects.filter(user=request.user, status='pending')
        referral_levels = build_referral_levels(profile)
        tier = get_user_tier(profile)
        config = SiteConfig.load()

        try:
            btc_price = get_btc_price()
            market = get_btc_market()
            btc_change = market['change']
        except Exception:
            btc_price = Decimal('0')
            btc_change = 0

        btc_equivalent = float(profile.available_balance / btc_price) if btc_price else 0

        today_profit = get_today_stack_profit(request.user)

        return Response({
            'profile': UserProfileSerializer(profile).data,
            'pending_deposits': {
                'total': float(pending_deposits.aggregate(Sum('amount'))['amount__sum'] or 0),
                'count': pending_deposits.count(),
            },
            'pending_withdrawals': {
                'total': float(pending_withdrawals.aggregate(Sum('amount'))['amount__sum'] or 0),
                'count': pending_withdrawals.count(),
            },
            'referral_levels': referral_levels,
            'referral_tier': tier['level'],
            'profit_percent': tier['profit_percent'],
            'today_profit': float(today_profit),
            'daily_bonus': get_daily_bonus_status(profile),
            'stats_trends': build_stats_trends(request.user),
            'btc_equivalent': round(btc_equivalent, 6),
            'btc_price': float(btc_price),
            'btc_change': btc_change,
            'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
            'site_config': {
                'min_deposit': float(config.min_deposit),
                'min_withdraw': float(config.min_withdraw),
                'referral_commission_percent': float(config.referral_commission_rate * 100),
                'investment_lock_days': config.investment_lock_days,
            },
        })


class StackView(views.APIView):
    def post(self, request):
        profile = request.user.profile
        if not profile.can_stack:
            return Response(
                {'error': 'You can only stack once every 24 hours.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if profile.total_balance <= 0:
            return Response(
                {'error': 'Insufficient balance to stack.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tier = get_user_tier(profile)
        profit_rate = tier['profit_rate']
        previous_balance = profile.total_balance
        stack_amount = previous_balance
        profit = (stack_amount * profit_rate).quantize(Decimal('0.01'))

        StackLog.objects.create(
            user=request.user,
            amount=stack_amount,
            profit_earned=profit,
            profit_rate=profit_rate,
        )
        profile.total_profit += profit
        profile.total_balance += profit
        profile.available_balance += profit
        profile.last_stack_at = timezone.now()
        profile.save()

        Transaction.objects.create(
            user=request.user,
            type='stack',
            amount=profit,
            description=f'Stacked ${stack_amount:.2f} at {tier["profit_percent"]} — earned ${profit:.2f}',
        )

        stack_data = {
            'stack_amount': float(stack_amount),
            'profit_earned': float(profit),
            'profit_rate': float(profit_rate),
            'profit_percent': tier['profit_percent'],
            'previous_balance': float(previous_balance),
            'new_balance': float(profile.total_balance),
            'referral_tier': tier['level'],
        }

        Notification.objects.create(
            user=request.user,
            title='Stack Successful',
            message=(
                f'You stacked ${stack_amount:.2f} and earned ${profit:.2f} '
                f'({tier["profit_percent"]} daily profit).'
            ),
            notification_type='stack',
            extra_data=stack_data,
        )

        return Response({
            'message': f'Successfully stacked! You earned ${profit:.2f} profit ({tier["profit_percent"]}).',
            'stack_result': stack_data,
            'profile': UserProfileSerializer(profile).data,
        })


class DepositCreateView(generics.CreateAPIView):
    serializer_class = DepositSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def perform_create(self, serializer):
        deposit = serializer.save(user=self.request.user)
        Transaction.objects.create(
            user=self.request.user,
            type='deposit',
            amount=deposit.amount,
            description=f'Deposit request ({deposit.network}) - {deposit.transaction_id}',
        )
        Notification.objects.create(
            user=self.request.user,
            title='Deposit Submitted',
            message=f'Your deposit request of ${deposit.amount} via {deposit.network} is pending review.',
            notification_type='deposit',
        )


class WithdrawalCreateView(generics.CreateAPIView):
    serializer_class = WithdrawalSerializer

    def create(self, request, *args, **kwargs):
        profile = request.user.profile
        release_expired_locks(profile)
        profile.refresh_from_db()

        amount = Decimal(str(request.data.get('amount', 0)))
        withdrawable = get_withdrawable_balance(profile)

        if Withdrawal.objects.filter(user=request.user, status='pending').exists():
            return Response(
                {'error': 'You already have a pending withdrawal. Wait until it is completed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount > withdrawable:
            locked = profile.locked_investment
            return Response(
                {
                    'error': (
                        f'Insufficient withdrawable balance. '
                        f'Available: ${withdrawable:.2f}. '
                        f'${locked:.2f} is locked for {SiteConfig.load().investment_lock_days} days.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        withdrawal = serializer.save(user=self.request.user)
        Transaction.objects.create(
            user=self.request.user,
            type='withdraw',
            amount=withdrawal.amount,
            description=f'Withdrawal request - {withdrawal.transaction_id}',
        )
        Notification.objects.create(
            user=self.request.user,
            title='Withdrawal Submitted',
            message=(
                f'Your withdrawal of ${withdrawal.amount} has been submitted. '
                f'Processing time: 24–72 hours.'
            ),
            notification_type='withdraw',
        )


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class DepositListView(generics.ListAPIView):
    serializer_class = DepositSerializer

    def get_queryset(self):
        return Deposit.objects.filter(user=self.request.user)


class WithdrawalListView(generics.ListAPIView):
    serializer_class = WithdrawalSerializer

    def get_queryset(self):
        return Withdrawal.objects.filter(user=self.request.user)


class StackLogListView(generics.ListAPIView):
    serializer_class = StackLogSerializer

    def get_queryset(self):
        return StackLog.objects.filter(user=self.request.user)[:20]


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class MarkNotificationReadView(views.APIView):
    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.is_read = True
            notification.save()
            return Response({'message': 'Marked as read.', 'notification': NotificationSerializer(notification).data})
        except Notification.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class MarketDataView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        timeframe = request.query_params.get('timeframe', '15m')
        try:
            return Response(get_btc_market(timeframe=timeframe))
        except Exception:
            return Response(
                {'error': 'Unable to fetch live market data. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


# Admin Views
class AdminDashboardView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.filter(is_staff=False).count()
        total_deposits = Deposit.objects.filter(status='approved').aggregate(Sum('amount'))['amount__sum'] or 0
        total_withdrawals = Withdrawal.objects.filter(status='approved').aggregate(Sum('amount'))['amount__sum'] or 0
        pending_deposits = Deposit.objects.filter(status='pending').count()
        pending_withdrawals = Withdrawal.objects.filter(status='pending').count()
        pending_deposit_amount = Deposit.objects.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or 0
        pending_withdrawal_amount = Withdrawal.objects.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or 0

        recent_deposits = AdminDepositSerializer(
            Deposit.objects.all().select_related('user').order_by('-created_at')[:5],
            many=True, context={'request': request},
        ).data
        recent_withdrawals = AdminWithdrawalSerializer(
            Withdrawal.objects.all().select_related('user').order_by('-created_at')[:5], many=True,
        ).data
        recent_users = AdminUserSerializer(
            User.objects.filter(is_staff=False).select_related('profile').order_by('-date_joined')[:5], many=True,
        ).data

        return Response({
            'total_users': total_users,
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'pending_deposits': pending_deposits,
            'pending_withdrawals': pending_withdrawals,
            'pending_deposit_amount': float(pending_deposit_amount),
            'pending_withdrawal_amount': float(pending_withdrawal_amount),
            'total_profit_paid': float(
                UserProfile.objects.aggregate(Sum('total_profit'))['total_profit__sum'] or 0,
            ),
            'recent_deposits': recent_deposits,
            'recent_withdrawals': recent_withdrawals,
            'recent_users': recent_users,
        })


class AdminSiteConfigView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(SiteConfigSerializer(SiteConfig.load()).data)

    def patch(self, request):
        config = SiteConfig.load()
        serializer = SiteConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.filter(is_staff=False).select_related('profile')


class AdminDepositListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminDepositSerializer
    queryset = Deposit.objects.all().select_related('user')

    def get_serializer_context(self):
        return {'request': self.request}


class AdminWithdrawalListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminWithdrawalSerializer
    queryset = Withdrawal.objects.all().select_related('user')


class AdminApproveDepositView(views.APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            deposit = Deposit.objects.get(pk=pk)
            if deposit.status != 'pending':
                return Response({'error': 'Already processed.'}, status=status.HTTP_400_BAD_REQUEST)
            deposit.status = 'approved'
            deposit.save()
            profile = deposit.user.profile
            profile.available_balance += deposit.amount
            profile.total_balance += deposit.amount
            profile.total_deposit += deposit.amount
            profile.save()

            create_investment_lock(deposit.user, deposit.amount)

            config = SiteConfig.load()
            commission_rate = config.referral_commission_rate or Decimal(str(settings.REFERRAL_BONUS_RATE))

            if profile.referred_by:
                bonus = (deposit.amount * commission_rate).quantize(Decimal('0.01'))
                referrer_profile = profile.referred_by
                referrer_profile.available_balance += bonus
                referrer_profile.total_balance += bonus
                referrer_profile.total_referral_bonus += bonus
                referrer_profile.save()
                Transaction.objects.create(
                    user=referrer_profile.user,
                    type='referral',
                    amount=bonus,
                    description=f'Referral commission ({float(commission_rate * 100):.0f}%) from {deposit.user.username}',
                )
                Notification.objects.create(
                    user=referrer_profile.user,
                    title='Referral Commission Earned',
                    message=f'You earned ${bonus:.2f} commission from a ${deposit.amount} deposit.',
                    notification_type='referral',
                )

            Notification.objects.create(
                user=deposit.user,
                title='Deposit Approved',
                message=(
                    f'Your deposit of ${deposit.amount} has been approved. '
                    f'Investment is locked for {config.investment_lock_days} days.'
                ),
                notification_type='deposit',
            )
            return Response({'message': 'Deposit approved.'})
        except Deposit.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminRejectDepositView(views.APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            deposit = Deposit.objects.get(pk=pk)
            deposit.status = 'rejected'
            deposit.save()
            Notification.objects.create(
                user=deposit.user,
                title='Deposit Rejected',
                message=f'Your deposit of ${deposit.amount} has been rejected.',
                notification_type='deposit',
            )
            return Response({'message': 'Deposit rejected.'})
        except Deposit.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminApproveWithdrawalView(views.APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            withdrawal = Withdrawal.objects.get(pk=pk)
            if withdrawal.status != 'pending':
                return Response({'error': 'Already processed.'}, status=status.HTTP_400_BAD_REQUEST)
            profile = withdrawal.user.profile
            release_expired_locks(profile)
            if withdrawal.amount > get_withdrawable_balance(profile):
                return Response({'error': 'User has insufficient withdrawable balance.'}, status=status.HTTP_400_BAD_REQUEST)
            withdrawal.status = 'approved'
            withdrawal.save()
            profile.available_balance -= withdrawal.amount
            profile.total_balance -= withdrawal.amount
            profile.total_withdraw += withdrawal.amount
            profile.save()
            Notification.objects.create(
                user=withdrawal.user,
                title='Withdrawal Approved',
                message=f'Your withdrawal of ${withdrawal.amount} has been approved and sent.',
                notification_type='withdraw',
            )
            return Response({'message': 'Withdrawal approved.'})
        except Withdrawal.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminRejectWithdrawalView(views.APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            withdrawal = Withdrawal.objects.get(pk=pk)
            withdrawal.status = 'rejected'
            withdrawal.save()
            Notification.objects.create(
                user=withdrawal.user,
                title='Withdrawal Rejected',
                message=f'Your withdrawal of ${withdrawal.amount} has been rejected.',
                notification_type='withdraw',
            )
            return Response({'message': 'Withdrawal rejected.'})
        except Withdrawal.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminTransactionListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminTransactionSerializer
    queryset = Transaction.objects.all().select_related('user').order_by('-created_at')


class AdminUserDetailView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            user = User.objects.select_related('profile').get(pk=pk)
            return Response(AdminUserSerializer(user).data)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        profile = user.profile

        if 'is_active' in data:
            user.is_active = data['is_active']
            user.save()

        if 'is_staff' in data and request.user.is_superuser:
            user.is_staff = data['is_staff']
            user.save()

        if 'vip_level' in data:
            profile.vip_level = data['vip_level']

        if 'adjust_balance' in data:
            amount = data['adjust_balance']
            profile.available_balance += amount
            profile.total_balance += amount
            note = data.get('note', 'Admin balance adjustment')
            Transaction.objects.create(
                user=user,
                type='deposit' if amount >= 0 else 'withdraw',
                amount=abs(amount),
                description=f'Admin adjustment: {note}',
            )
            Notification.objects.create(
                user=user,
                title='Balance Updated',
                message=f'Your balance was adjusted by ${amount:.2f}. {note}',
            )

        profile.save()
        user.refresh_from_db()
        return Response(AdminUserSerializer(user).data)


class AdminNotifyUserView(views.APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminNotifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Notification.objects.create(
            user=user,
            title=serializer.validated_data['title'],
            message=serializer.validated_data['message'],
        )
        return Response({'message': 'Notification sent.'})
