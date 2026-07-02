from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile, Deposit, Withdrawal, StackLog, Transaction, Notification
from .market_service import get_btc_market, get_btc_price
from .utils import build_stats_trends, build_referral_levels
from .serializers import (
    RegisterSerializer, UserProfileSerializer, DepositSerializer,
    WithdrawalSerializer, StackLogSerializer, TransactionSerializer,
    NotificationSerializer, AdminUserSerializer, AdminDepositSerializer,
    AdminWithdrawalSerializer, AdminTransactionSerializer,
    AdminUserUpdateSerializer, AdminNotifySerializer,
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


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user.profile


class DashboardView(views.APIView):
    def get(self, request):
        profile = request.user.profile
        pending_deposits = Deposit.objects.filter(user=request.user, status='pending')
        pending_withdrawals = Withdrawal.objects.filter(user=request.user, status='pending')

        referral_levels = build_referral_levels(profile)

        try:
            btc_price = get_btc_price()
            market = get_btc_market()
            btc_change = market['change']
        except Exception:
            btc_price = Decimal('0')
            btc_change = 0

        btc_equivalent = float(profile.available_balance / btc_price) if btc_price else 0

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
            'stats_trends': build_stats_trends(request.user),
            'btc_equivalent': round(btc_equivalent, 6),
            'btc_price': float(btc_price),
            'btc_change': btc_change,
            'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        })


class StackView(views.APIView):
    def post(self, request):
        profile = request.user.profile
        if not profile.can_stack:
            return Response(
                {'error': 'You can only stack once every 24 hours.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if profile.available_balance <= 0:
            return Response(
                {'error': 'Insufficient balance to stack.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profit_rate = Decimal(str(settings.STACK_DAILY_PROFIT_RATE))
        stack_amount = profile.available_balance
        profit = stack_amount * profit_rate

        StackLog.objects.create(
            user=request.user,
            amount=stack_amount,
            profit_earned=profit,
        )
        profile.total_profit += profit
        profile.total_balance += profit
        profile.available_balance += profit
        profile.last_stack_at = timezone.now()
        profile.save()

        Transaction.objects.create(
            user=request.user,
            type='stack',
            amount=stack_amount,
            description=f'Stacked balance - earned ${profit:.2f} profit',
        )
        Notification.objects.create(
            user=request.user,
            title='Stack Successful',
            message=f'You stacked ${stack_amount:.2f} and earned ${profit:.2f} profit!',
        )

        return Response({
            'message': f'Successfully stacked! You earned ${profit:.2f} profit.',
            'profile': UserProfileSerializer(profile).data,
        })


class DepositCreateView(generics.CreateAPIView):
    serializer_class = DepositSerializer

    def perform_create(self, serializer):
        deposit = serializer.save(user=self.request.user)
        Transaction.objects.create(
            user=self.request.user,
            type='deposit',
            amount=deposit.amount,
            description=f'Deposit request - {deposit.transaction_id}',
        )
        Notification.objects.create(
            user=self.request.user,
            title='Deposit Submitted',
            message=f'Your deposit request of ${deposit.amount} has been submitted and is pending review.',
        )


class WithdrawalCreateView(generics.CreateAPIView):
    serializer_class = WithdrawalSerializer

    def create(self, request, *args, **kwargs):
        profile = request.user.profile
        amount = Decimal(str(request.data.get('amount', 0)))
        if amount > profile.available_balance:
            return Response(
                {'error': 'Insufficient balance.'},
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
            message=f'Your withdrawal request of ${withdrawal.amount} has been submitted and is pending review.',
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
            return Response({'message': 'Marked as read.'})
        except Notification.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class MarketDataView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        timeframe = request.query_params.get('timeframe', '15m')
        try:
            return Response(get_btc_market(timeframe=timeframe))
        except Exception as exc:
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
            Deposit.objects.all().select_related('user').order_by('-created_at')[:5], many=True
        ).data
        recent_withdrawals = AdminWithdrawalSerializer(
            Withdrawal.objects.all().select_related('user').order_by('-created_at')[:5], many=True
        ).data
        recent_users = AdminUserSerializer(
            User.objects.filter(is_staff=False).select_related('profile').order_by('-date_joined')[:5], many=True
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
                UserProfile.objects.aggregate(Sum('total_profit'))['total_profit__sum'] or 0
            ),
            'recent_deposits': recent_deposits,
            'recent_withdrawals': recent_withdrawals,
            'recent_users': recent_users,
        })


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.filter(is_staff=False).select_related('profile')


class AdminDepositListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminDepositSerializer
    queryset = Deposit.objects.all().select_related('user')


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

            if profile.referred_by:
                bonus_rate = Decimal(str(settings.REFERRAL_BONUS_RATE))
                bonus = deposit.amount * bonus_rate
                referrer_profile = profile.referred_by
                referrer_profile.available_balance += bonus
                referrer_profile.total_balance += bonus
                referrer_profile.total_referral_bonus += bonus
                referrer_profile.save()
                Transaction.objects.create(
                    user=referrer_profile.user,
                    type='referral',
                    amount=bonus,
                    description=f'Level 1 referral bonus from {deposit.user.username}',
                )
                Notification.objects.create(
                    user=referrer_profile.user,
                    title='Referral Bonus Earned',
                    message=f'You earned ${bonus:.2f} referral bonus from a deposit.',
                )

            Notification.objects.create(
                user=deposit.user,
                title='Deposit Approved',
                message=f'Your deposit of ${deposit.amount} has been approved.',
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
            if withdrawal.amount > profile.available_balance:
                return Response({'error': 'User has insufficient balance.'}, status=status.HTTP_400_BAD_REQUEST)
            withdrawal.status = 'approved'
            withdrawal.save()
            profile.available_balance -= withdrawal.amount
            profile.total_withdraw += withdrawal.amount
            profile.save()
            Notification.objects.create(
                user=withdrawal.user,
                title='Withdrawal Approved',
                message=f'Your withdrawal of ${withdrawal.amount} has been approved.',
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
            user = User.objects.filter(is_staff=False).select_related('profile').get(pk=pk)
            return Response(AdminUserSerializer(user).data)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            user = User.objects.filter(is_staff=False).get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        profile = user.profile

        if 'is_active' in data:
            user.is_active = data['is_active']
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
            user = User.objects.get(pk=pk, is_staff=False)
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
