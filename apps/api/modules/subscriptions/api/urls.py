from django.urls import path

from . import views

urlpatterns = [
    path(
        "plans/",
        views.PlanListView.as_view(),
        name="plan-list",
    ),
    path(
        "current/",
        views.CurrentSubscriptionView.as_view(),
        name="current-subscription",
    ),
    path(
        "pay/",
        views.CreatePaymentView.as_view(),
        name="create-payment",
    ),
    path(
        "payments/",
        views.PaymentHistoryView.as_view(),
        name="payment-history",
    ),
]
