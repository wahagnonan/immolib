from django.urls import path

from .views import AccountPreferencesView

urlpatterns = [
    path(
        "preferences/",
        AccountPreferencesView.as_view(),
        name="i18n-account-preferences",
    ),
]
