from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('config/', views.SiteConfigView.as_view(), name='site-config'),
    path('stack/', views.StackView.as_view(), name='stack'),
    path('stack/logs/', views.StackLogListView.as_view(), name='stack-logs'),
    path('deposits/', views.DepositCreateView.as_view(), name='deposit-create'),
    path('deposits/list/', views.DepositListView.as_view(), name='deposit-list'),
    path('withdrawals/', views.WithdrawalCreateView.as_view(), name='withdrawal-create'),
    path('withdrawals/list/', views.WithdrawalListView.as_view(), name='withdrawal-list'),
    path('transactions/', views.TransactionListView.as_view(), name='transactions'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.MarkNotificationReadView.as_view(), name='notification-read'),
    path('market/', views.MarketDataView.as_view(), name='market'),
    # Admin
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/config/', views.AdminSiteConfigView.as_view(), name='admin-config'),
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-users'),
    path('admin/deposits/', views.AdminDepositListView.as_view(), name='admin-deposits'),
    path('admin/withdrawals/', views.AdminWithdrawalListView.as_view(), name='admin-withdrawals'),
    path('admin/deposits/<int:pk>/approve/', views.AdminApproveDepositView.as_view(), name='admin-approve-deposit'),
    path('admin/deposits/<int:pk>/reject/', views.AdminRejectDepositView.as_view(), name='admin-reject-deposit'),
    path('admin/withdrawals/<int:pk>/approve/', views.AdminApproveWithdrawalView.as_view(), name='admin-approve-withdrawal'),
    path('admin/withdrawals/<int:pk>/reject/', views.AdminRejectWithdrawalView.as_view(), name='admin-reject-withdrawal'),
    path('admin/transactions/', views.AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:pk>/notify/', views.AdminNotifyUserView.as_view(), name='admin-notify-user'),
]
