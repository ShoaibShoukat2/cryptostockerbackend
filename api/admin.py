from django.contrib import admin
from .models import (
    UserProfile, Deposit, Withdrawal, StackLog, Transaction,
    Notification, SiteConfig, InvestmentLock, DailyReferralTracker, ContactMessage,
)


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ['bep20_address', 'trc20_address', 'telegram_link', 'updated_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'plain_password', 'referral_code', 'vip_level', 'available_balance', 'locked_investment', 'total_deposit']
    search_fields = ['user__username', 'referral_code', 'plain_password']


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'network', 'status', 'created_at']
    list_filter = ['status', 'network']


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at']
    list_filter = ['status']


admin.site.register(StackLog)
admin.site.register(Transaction)
admin.site.register(Notification)
admin.site.register(InvestmentLock)
admin.site.register(DailyReferralTracker)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read']
    search_fields = ['user__username', 'subject', 'message']
