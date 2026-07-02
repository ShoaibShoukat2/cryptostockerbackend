from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile, Deposit, Withdrawal, StackLog, Transaction, Notification


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

    class Meta:
        model = UserProfile
        fields = [
            'user', 'referral_code', 'vip_level', 'available_balance',
            'total_balance', 'total_deposit', 'total_withdraw', 'total_profit',
            'total_referral_bonus', 'total_referrals', 'active_referrals',
            'can_stack', 'next_stack_in_seconds', 'last_stack_at', 'created_at',
        ]


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
            except UserProfile.DoesNotExist:
                pass
        Notification.objects.create(
            user=user,
            title='Welcome to Crypto Stacker',
            message='Your account is ready. Deposit funds and start stacking to earn daily profits.',
        )
        return user


class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = ['id', 'amount', 'status', 'transaction_id', 'note', 'created_at']
        read_only_fields = ['status', 'transaction_id', 'created_at']


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = ['id', 'amount', 'status', 'wallet_address', 'transaction_id', 'note', 'created_at']
        read_only_fields = ['status', 'transaction_id', 'created_at']


class StackLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StackLog
        fields = ['id', 'amount', 'profit_earned', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'amount', 'description', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'is_read', 'created_at']


class AdminUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined', 'profile']


class AdminDepositSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Deposit
        fields = ['id', 'username', 'amount', 'status', 'transaction_id', 'note', 'created_at', 'updated_at']


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
    adjust_balance = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class AdminNotifySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
