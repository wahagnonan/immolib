"""Routes d'abonnement."""

from django.urls import path

from .views import (
    CancelSubscriptionView,
    PayDunyaWebhookView,
    SubscriptionExpiryCheckView,
    SubscriptionPlansView,
    SubscriptionTransactionRefreshView,
    SubscriptionView,
    UpgradeSubscriptionView,
)

urlpatterns = [
    path("subscription/", SubscriptionView.as_view(), name="subscription-detail"),
    path(
        "subscription/plans/",
        SubscriptionPlansView.as_view(),
        name="subscription-plans",
    ),
    path(
        "subscription/upgrade/",
        UpgradeSubscriptionView.as_view(),
        name="subscription-upgrade",
    ),
    path(
        "subscription/cancel/",
        CancelSubscriptionView.as_view(),
        name="subscription-cancel",
    ),
    path(
        "subscription/transactions/<uuid:transaction_id>/refresh/",
        SubscriptionTransactionRefreshView.as_view(),
        name="subscription-transaction-refresh",
    ),
    path(
        "subscription/expiry-check/",
        SubscriptionExpiryCheckView.as_view(),
        name="subscription-expiry-check",
    ),
    path(
        "webhooks/paydunya/",
        PayDunyaWebhookView.as_view(),
        name="paydunya-webhook",
    ),
]
