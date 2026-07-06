from rest_framework import serializers
from django.contrib.auth.models import User
from django.conf import settings
from .models import (
    UserProfile, Deposit, Withdrawal, StackLog, Transaction,
    Notification, SiteConfig, ContactMessage,
)
from .business_logic import get_withdrawable_balance, get_user_tier


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
            'user', 'email', 'referral_code', 'vip_level', 'available_balance',
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


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128)
    referral_code = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError('Username is required.')
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError('Username already taken.')
        return username

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exclude(email='').exists():
            raise serializers.ValidationError('Email already registered.')
        return email

    def create(self, validated_data):
        password = validated_data['password']
        email = validated_data['email']
        referral_code = validated_data.pop('referral_code', '')
        user = User.objects.create(
            username=validated_data['username'],
            email=email,
        )
        user.set_unusable_password()
        user.save()
        user.profile.plain_password = password
        user.profile.email = email
        user.profile.save(update_fields=['plain_password', 'email'])
        if referral_code:
            try:
                referrer = UserProfile.objects.get(referral_code=referral_code.upper())
                user.profile.referred_by = referrer
                user.profile.save(update_fields=['referred_by'])
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

    def validate(self, attrs):
        if self.instance is not None:
            return attrs
        request = self.context.get('request')
        screenshot = attrs.get('screenshot') or (request and request.FILES.get('screenshot'))
        if not screenshot:
            raise serializers.ValidationError({
                'screenshot': 'Payment screenshot is required to submit a deposit request.',
            })
        return attrs


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = ['id', 'amount', 'network', 'status', 'wallet_address', 'transaction_id', 'note', 'created_at']
        read_only_fields = ['status', 'transaction_id', 'created_at']

    def validate_amount(self, value):
        config = SiteConfig.load()
        min_wd = config.min_withdraw or settings.MIN_WITHDRAW
        if value < min_wd:
            raise serializers.ValidationError(f'Minimum withdrawal is ${min_wd}.')
        return value

    def validate_network(self, value):
        if value not in ('BEP20', 'TRC20'):
            raise serializers.ValidationError('Network must be BEP20 or TRC20.')
        return value

    def validate_wallet_address(self, value):
        address = (value or '').strip()
        if not address:
            raise serializers.ValidationError('Wallet address is required.')
        return address


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


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'subject', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'is_read', 'created_at']


class AdminContactMessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ContactMessage
        fields = ['id', 'username', 'email', 'subject', 'message', 'is_read', 'created_at']


class SiteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = [
            'bep20_address', 'trc20_address', 'telegram_link',
            'support_heading', 'support_subtitle',
            'min_deposit', 'min_withdraw', 'referral_commission_rate',
            'daily_bonus_amount', 'daily_bonus_referrals', 'investment_lock_days',
            'promotion_bonus_subtitle', 'promotion_bonus_note',
            'promotion_tier1_detail', 'promotion_tier1_reward',
            'promotion_tier2_detail', 'promotion_tier2_reward',
            'promotion_tier3_detail', 'promotion_tier3_reward',
            'about_text',
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    plain_password = serializers.CharField(source='profile.plain_password', read_only=True)
    email = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'plain_password', 'is_active', 'is_staff', 'date_joined', 'profile',
        ]

    def get_email(self, obj):
        profile_email = getattr(obj.profile, 'email', '') or ''
        return profile_email or obj.email or ''


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
        fields = [
            'id', 'username', 'amount', 'network', 'status', 'wallet_address',
            'transaction_id', 'note', 'created_at', 'updated_at',
        ]


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
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(max_length=128, required=False, write_only=True)
    confirm_password = serializers.CharField(max_length=128, required=False, write_only=True)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError('Username is required.')
        return username

    def validate(self, data):
        password = data.get('password')
        confirm = data.get('confirm_password')
        if password or confirm:
            if not password or not confirm:
                raise serializers.ValidationError('Both password and confirm_password are required.')
            if password != confirm:
                raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
            if len(password) < 4:
                raise serializers.ValidationError({'password': 'Password must be at least 4 characters.'})
        return data


class AdminNotifySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()


class AdminAccountCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)
    confirm_password = serializers.CharField(max_length=128, write_only=True)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError('Username is required.')
        return username

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        if len(data['password']) < 4:
            raise serializers.ValidationError({'password': 'Password must be at least 4 characters.'})
        return data


class AdminAccountUpdateSerializer(serializers.Serializer):
    admin_id = serializers.IntegerField(required=False)
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(max_length=128, required=False, write_only=True)
    confirm_password = serializers.CharField(max_length=128, required=False, write_only=True)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError('Username is required.')
        return username

    def validate(self, data):
        password = data.get('password')
        confirm = data.get('confirm_password')
        if password or confirm:
            if not password or not confirm:
                raise serializers.ValidationError('Both password and confirm_password are required.')
            if password != confirm:
                raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
            if len(password) < 4:
                raise serializers.ValidationError({'password': 'Password must be at least 4 characters.'})
        if not data.get('username') and not password:
            raise serializers.ValidationError('Provide a new username and/or password.')
        return data
