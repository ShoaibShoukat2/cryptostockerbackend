from django.contrib import admin
from django.contrib.auth.models import User
from .models import UserProfile, Deposit, Withdrawal, StackLog, Transaction, Notification


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'vip_level', 'available_balance', 'total_balance', 'referral_code']
    search_fields = ['user__username', 'referral_code']


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at']
    list_filter = ['status']


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at']
    list_filter = ['status']


admin.site.register(StackLog)
admin.site.register(Transaction)
admin.site.register(Notification)

admin.site.site_header = 'Crypto Stacker Admin'
admin.site.site_title = 'Crypto Stacker'
