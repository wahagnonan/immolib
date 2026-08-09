from django.urls import path

from .views import (
    AdminAuditLogListView,
    AdminDashboardView,
    AdminHouseListView,
    AdminLandlordListView,
    AdminNotificationListView,
    AdminPaymentListView,
    AdminSubscriptionActionView,
    AdminSubscriptionListView,
    AdminTenantListView,
    AdminUserDetailView,
    AdminUserListView,
    AdminUserStatusView,
    HousesEvolutionView,
    RevenueSeriesView,
    UsersEvolutionView,
)

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("stats/users-evolution/", UsersEvolutionView.as_view(), name="admin-stats-users"),
    path("stats/revenue/", RevenueSeriesView.as_view(), name="admin-stats-revenue"),
    path("stats/houses/", HousesEvolutionView.as_view(), name="admin-stats-houses"),
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    path("users/<uuid:user_id>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path(
        "users/<uuid:user_id>/status/",
        AdminUserStatusView.as_view(),
        name="admin-user-status",
    ),
    path("landlords/", AdminLandlordListView.as_view(), name="admin-landlords"),
    path("tenants/", AdminTenantListView.as_view(), name="admin-tenants"),
    path("houses/", AdminHouseListView.as_view(), name="admin-houses"),
    path("subscriptions/", AdminSubscriptionListView.as_view(), name="admin-subscriptions"),
    path(
        "subscriptions/<uuid:subscription_id>/",
        AdminSubscriptionActionView.as_view(),
        name="admin-subscription-action",
    ),
    path("payments/", AdminPaymentListView.as_view(), name="admin-payments"),
    path("notifications/", AdminNotificationListView.as_view(), name="admin-notifications"),
    path("audit-logs/", AdminAuditLogListView.as_view(), name="admin-audit-logs"),
]
