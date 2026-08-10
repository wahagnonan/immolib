from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AccountOtpChallenge
from ..throttles import (
    LoginEmailThrottle,
    OtpConfirmPhoneThrottle,
    OtpRequestPhoneThrottle,
    PublicAuthIpThrottle,
    RegisterIpThrottle,
    RegisterPhoneThrottle,
)
from ..services import (
    INVALID_ACCOUNT_OTP_MESSAGE,
    InvalidAccountOtp,
    RegisterUserData,
    confirm_password_reset,
    confirm_email_verification,
    confirm_phone_verification,
    login_is_locked,
    record_login_failure,
    record_login_success,
    register_user,
    request_account_otp,
)
from .serializers import (
    CurrentUserSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PhoneCodeSerializer,
    PhoneOnlySerializer,
    RegisterSerializer,
)


User = get_user_model()
GENERIC_OTP_SENT = _("Si le compte est éligible, un code a été mis en file d’envoi.")


def _user_response(user) -> dict:
    return {"user": CurrentUserSerializer(user).data}


def _otp_request_payload(issue=None) -> dict:
    payload = {"detail": GENERIC_OTP_SENT}
    if issue is not None:
        payload["verification_channel"] = issue.challenge.channel
        if issue.challenge.channel == AccountOtpChallenge.Channel.EMAIL:
            name, domain = issue.challenge.destination.split("@", 1)
            payload["masked_destination"] = f"{name[:2]}***@{domain}"
        else:
            payload["masked_destination"] = f"***{issue.challenge.destination[-4:]}"
    if (
        settings.EXPOSE_TEST_OTP
        and issue is not None
        and issue.challenge.consumed_at is None
        and issue.challenge.expires_at > timezone.now()
        and issue.code
    ):
        payload["otp_code"] = issue.code
    return payload


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfCookieView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (
        PublicAuthIpThrottle,
        RegisterIpThrottle,
        RegisterPhoneThrottle,
    )

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            result = register_user(
                data=RegisterUserData(
                    phone=values["phone"],
                    password=values["password"],
                    first_name=values.get("first_name", ""),
                    last_name=values.get("last_name", ""),
                    email=values.get("email", ""),
                    tenant_invitation_token=values.get(
                        "tenant_invitation_token", ""
                    ),
                )
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError(exc.messages) from exc

        payload = {
            **_user_response(result.user),
            **_otp_request_payload(result.otp_issue),
            "verification_required": True,
            "verification_channel": result.verification_channel,
        }
        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class PhoneVerificationRequestView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, OtpRequestPhoneThrottle)

    def post(self, request: Request) -> Response:
        serializer = PhoneOnlySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = request_account_otp(
            phone=serializer.validated_data["phone"],
            purpose=AccountOtpChallenge.Purpose.PHONE_VERIFICATION,
        )
        return Response(_otp_request_payload(issue))


@method_decorator(csrf_protect, name="dispatch")
class PhoneVerificationConfirmView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, OtpConfirmPhoneThrottle)

    def post(self, request: Request) -> Response:
        serializer = PhoneCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = confirm_phone_verification(**serializer.validated_data)
        except InvalidAccountOtp as exc:
            raise ValidationError({"detail": INVALID_ACCOUNT_OTP_MESSAGE}) from exc
        login(request, user)
        return Response(_user_response(user))


@method_decorator(csrf_protect, name="dispatch")
class EmailVerificationRequestView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, OtpRequestPhoneThrottle)

    def post(self, request: Request) -> Response:
        serializer = PhoneOnlySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = request_account_otp(
            phone=serializer.validated_data["phone"],
            purpose=AccountOtpChallenge.Purpose.EMAIL_VERIFICATION,
        )
        return Response(_otp_request_payload(issue))


@method_decorator(csrf_protect, name="dispatch")
class EmailVerificationConfirmView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, OtpConfirmPhoneThrottle)

    def post(self, request: Request) -> Response:
        serializer = PhoneCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = confirm_email_verification(**serializer.validated_data)
        except InvalidAccountOtp as exc:
            raise ValidationError({"detail": INVALID_ACCOUNT_OTP_MESSAGE}) from exc
        login(request, user)
        return Response(_user_response(user))


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, OtpRequestPhoneThrottle)

    def post(self, request: Request) -> Response:
        serializer = PhoneOnlySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = request_account_otp(
            phone=serializer.validated_data["phone"],
            purpose=AccountOtpChallenge.Purpose.PASSWORD_RESET,
        )
        return Response(_otp_request_payload(issue))


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetConfirmView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, OtpConfirmPhoneThrottle)

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            confirm_password_reset(
                phone=values["phone"],
                code=values["code"],
                password=values["password"],
            )
        except InvalidAccountOtp as exc:
            raise ValidationError({"detail": INVALID_ACCOUNT_OTP_MESSAGE}) from exc
        return Response({"detail": _("Votre mot de passe a été modifié.")})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (PublicAuthIpThrottle, LoginEmailThrottle)

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if login_is_locked(email=serializer.validated_data["email"]):
            raise ValidationError(
                {
                    "detail": _(
                        "Trop de tentatives échouées. Réessayez dans quelques minutes."
                    )
                }
            )
        user = (
            User.objects.filter(
                email__iexact=serializer.validated_data["email"],
                is_active=True,
            ).first()
        )
        if user is not None:
            user = authenticate(
                request=request,
                username=user.phone,
                password=serializer.validated_data["password"],
            )
        if user is None:
            record_login_failure(email=serializer.validated_data["email"])
            raise ValidationError({"detail": _("Email ou mot de passe incorrect.")})
        record_login_success(email=serializer.validated_data["email"])
        if not user.has_verified_contact:
            return Response(
                {
                    "detail": _(
                        "Vérifiez votre email ou votre téléphone avant de vous connecter."
                    ),
                    "contact_verification_required": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        from modules.properties.services import accept_pending_coowner_invitations
        from modules.leases.services import accept_pending_tenant_invitations

        if user.phone_verified_at is not None:
            accept_pending_coowner_invitations(user=user)
        accept_pending_tenant_invitations(user=user)
        login(request, user)
        if user.role == User.Role.ADMIN:
            from modules.admin_panel.audit import log_admin_action
            from modules.admin_panel.models import AuditLog

            log_admin_action(
                admin=user,
                action=AuditLog.Action.ADMIN_LOGIN,
                metadata={"session": True},
                request=request,
            )
        return Response(_user_response(user), status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        return Response(_user_response(request.user))


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
