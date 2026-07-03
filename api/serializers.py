from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from .models import (
    UserProfile, Deposit, Withdrawal, StackLog, Transaction,
    Notification, SiteConfig,
)
from .business_logic import get_withdrawable_balance, get_user_tier, track_referral_signup


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_referrals = serializers.IntegerField(read_only=True)
    active_referrals = serializers.IntegerField(read_only=True)
    can_stack = serializers.BooleanField(read_only=True)
    next_stack_in_seconds = serializers.IntegerField(read_only=True)
    withdrawable_balance = serializers.SerializerMethodField()
    locked_investment = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit_rate = serializers.SerializerMethodField()
    profit_percent = serializers.SerializerMethodField()
    referral_tier = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user', 'referral_code', 'vip_level', 'available_balance',
            'total_balance', 'locked_investment', 'withdrawable_balance',
            'total_deposit', 'total_withdraw', 'total_profit',
            'total_referral_bonus', 'total_referrals', 'active_referrals',
            'can_stack', 'next_stack_in_seconds', 'last_stack_at',
            'profit_rate', 'profit_percent', 'referral_tier', 'created_at',
        ]

    def get_withdrawable_balance(self, obj):
        return float(get_withdrawable_balance(obj))

    def get_profit_rate(self, obj):
        return float(get_user_tier(obj)['profit_rate'])

    def get_profit_percent(self, obj):
        return get_user_tier(obj)['profit_percent']

    def get_referral_tier(self, obj):
        return get_user_tier(obj)['level']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    referral_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name', 'referral_code']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        referral_code = validated_data.pop('referral_code', '')
        validated_data.pop('password2')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        if referral_code:
            try:
                referrer = UserProfile.objects.get(referral_code=referral_code.upper())
                user.profile.referred_by = referrer
                user.profile.save()
                track_referral_signup(referrer, user.username)
            except UserProfile.DoesNotExist:
                pass
        Notification.objects.create(
            user=user,
            title='Welcome to Crypto Stacker',
            message='Your account is ready. Deposit funds and start stacking to earn daily profits.',
        )
        return user


class DepositSerializer(serializers.ModelSerializer):
    screenshot_url = serializers.SerializerMethodField()

    class Meta:
        model = Deposit
        fields = [
            'id', 'amount', 'network', 'screenshot', 'screenshot_url',
            'status', 'transaction_id', 'note', 'created_at',
        ]
        read_only_fields = ['status', 'transaction_id', 'created_at', 'screenshot_url']

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return None

    def validate_amount(self, value):
        config = SiteConfig.load()
        min_dep = config.min_deposit or settings.MIN_DEPOSIT
        if value < min_dep:
            raise serializers.ValidationError(f'Minimum deposit is ${min_dep}.')
        return value


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = ['id', 'amount', 'status', 'wallet_address', 'transaction_id', 'note', 'created_at']
        read_only_fields = ['status', 'transaction_id', 'created_at']

    def validate_amount(self, value):
        config = SiteConfig.load()
        min_wd = config.min_withdraw or settings.MIN_WITHDRAW
        if value < min_wd:
            raise serializers.ValidationError(f'Minimum withdrawal is ${min_wd}.')
        return value


class StackLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StackLog
        fields = ['id', 'amount', 'profit_earned', 'profit_rate', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'amount', 'description', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'extra_data', 'is_read', 'created_at']


class SiteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = [
            'bep20_address', 'trc20_address', 'telegram_link',
            'min_deposit', 'min_withdraw', 'referral_commission_rate',
            'daily_bonus_amount', 'daily_bonus_referrals', 'investment_lock_days',
            'about_text',
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined', 'profile']


class AdminDepositSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    screenshot_url = serializers.SerializerMethodField()

    class Meta:
        model = Deposit
        fields = [
            'id', 'username', 'amount', 'network', 'screenshot', 'screenshot_url',
            'status', 'transaction_id', 'note', 'created_at', 'updated_at',
        ]

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return None


class AdminWithdrawalSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Withdrawal
        fields = ['id', 'username', 'amount', 'status', 'wallet_address', 'transaction_id', 'note', 'created_at', 'updated_at']


class AdminTransactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'username', 'type', 'amount', 'description', 'created_at']


class AdminUserUpdateSerializer(serializers.Serializer):
    vip_level = serializers.IntegerField(min_value=1, max_value=5, required=False)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    adjust_balance = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class AdminNotifySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
