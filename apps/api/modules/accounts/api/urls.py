from django.urls import path

from .views import (
    CsrfCookieView,
    CurrentUserView,
    EmailVerificationConfirmView,
    EmailVerificationRequestView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PhoneVerificationConfirmView,
    PhoneVerificationRequestView,
    RegisterView,
)


urlpatterns = [
    path("csrf/", CsrfCookieView.as_view(), name="auth-csrf"),
    path("register/", RegisterView.as_view(), name="auth-register"),
    path(
        "phone-verification/request/",
        PhoneVerificationRequestView.as_view(),
        name="auth-phone-verification-request",
    ),
    path(
        "phone-verification/confirm/",
        PhoneVerificationConfirmView.as_view(),
        name="auth-phone-verification-confirm",
    ),
    path(
        "email-verification/request/",
        EmailVerificationRequestView.as_view(),
        name="auth-email-verification-request",
    ),
    path(
        "email-verification/confirm/",
        EmailVerificationConfirmView.as_view(),
        name="auth-email-verification-confirm",
    ),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
