from django.urls import path

from .views import NotificationPreferenceView, PushSubscriptionView


urlpatterns = [
    path(
        "notification-preferences/",
        NotificationPreferenceView.as_view(),
        name="notification-preferences",
    ),
    path(
        "push-subscriptions/",
        PushSubscriptionView.as_view(),
        name="push-subscriptions",
    ),
]
