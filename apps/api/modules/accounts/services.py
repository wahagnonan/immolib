import secrets
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from hmac import compare_digest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext_lazy as _

from modules.i18n.utils import resolve_language

from .models import AccountOtpChallenge
from .phones import normalize_e164


User = get_user_model()
ACCOUNT_OTP_CODE_SALT = "immolib.account-otp-code.v2"
INVALID_ACCOUNT_OTP_MESSAGE = _("Code invalide ou expiré.")


def _login_lockout_key(email: str) -> str:
    return "immolib.login-lockout:" + sha256(
        email.strip().casefold().encode()
    ).hexdigest()


def login_is_locked(*, email: str) -> bool:
    failures = cache.get(_login_lockout_key(email), 0)
    return failures >= settings.LOGIN_LOCKOUT_MAX_ATTEMPTS


def record_login_failure(*, email: str) -> None:
    key = _login_lockout_key(email)
    failures = cache.get(key, 0) + 1
    if failures >= settings.LOGIN_LOCKOUT_MAX_ATTEMPTS:
        timeout = settings.LOGIN_LOCKOUT_DURATION_SECONDS
    else:
        timeout = settings.LOGIN_LOCKOUT_WINDOW_SECONDS
    cache.set(key, failures, timeout=timeout)


def record_login_success(*, email: str) -> None:
    cache.delete(_login_lockout_key(email))


class InvalidAccountOtp(Exception):
    """Erreur volontairement générique pour ne pas divulguer l'état d'un compte."""


@dataclass(frozen=True)
class RegisterUserData:
    phone: str
    password: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    tenant_invitation_token: str = ""


@dataclass(frozen=True)
class AccountOtpIssue:
    challenge: AccountOtpChallenge
    created: bool
    code: str = ""


@dataclass(frozen=True)
class RegistrationResult:
    user: object
    otp_issue: AccountOtpIssue
    verification_channel: str


def _account_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _account_otp_code_hash(challenge_id: str, code: str) -> str:
    return salted_hmac(
        ACCOUNT_OTP_CODE_SALT, f"{challenge_id}:{code.strip()}"
    ).hexdigest()


def account_otp_message_content(
    challenge: AccountOtpChallenge, code: str
) -> tuple[str, str]:
    """Sujet et corps figes a la mise en file de la notification."""
    if challenge.purpose == AccountOtpChallenge.Purpose.PASSWORD_RESET:
        subject = _("Réinitialisation de votre mot de passe ImmoLib")
        action = _("réinitialiser votre mot de passe")
    elif challenge.purpose == AccountOtpChallenge.Purpose.EMAIL_VERIFICATION:
        subject = _("Vérification de votre email ImmoLib")
        action = _("vérifier votre adresse email")
    else:
        subject = _("Vérification de votre téléphone ImmoLib")
        action = _("vérifier votre numéro de téléphone")
    body = _(
        "Votre code ImmoLib pour {action} est {code}. "
        "Il expire à {expires_at}. Ne le partagez avec personne."
    ).format(
        action=action,
        code=code,
        expires_at=timezone.localtime(challenge.expires_at).strftime("%H:%M"),
    )
    return subject, body


def _otp_route(*, user, purpose: str) -> tuple[str, str]:
    if purpose == AccountOtpChallenge.Purpose.EMAIL_VERIFICATION:
        if not user.email:
            raise ValidationError({"email": _("Une adresse email est obligatoire.")})
        return AccountOtpChallenge.Channel.EMAIL, user.email
    if purpose == AccountOtpChallenge.Purpose.PHONE_VERIFICATION:
        return AccountOtpChallenge.Channel.SMS, user.phone
    if purpose == AccountOtpChallenge.Purpose.PASSWORD_RESET:
        if user.email and user.email_verified_at is not None:
            return AccountOtpChallenge.Channel.EMAIL, user.email
        return AccountOtpChallenge.Channel.SMS, user.phone
    raise ValueError(_("Finalité OTP inconnue."))


@transaction.atomic
def issue_account_otp(*, user, purpose: str, now=None) -> AccountOtpIssue:
    """Crée au plus un nouveau code par fenêtre de refroidissement."""

    from modules.documents.models import NotificationDelivery

    now = now or timezone.now()
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    latest = (
        AccountOtpChallenge.objects.filter(user=locked_user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    cooldown = timedelta(seconds=settings.ACCOUNT_OTP_COOLDOWN_SECONDS)
    if latest and latest.created_at > now - cooldown:
        return AccountOtpIssue(challenge=latest, created=False)

    from django.utils import translation

    AccountOtpChallenge.objects.filter(
        user=locked_user,
        purpose=purpose,
        consumed_at__isnull=True,
    ).update(consumed_at=now)
    code = _account_otp_code()
    challenge = AccountOtpChallenge.objects.create(
        user=locked_user,
        purpose=purpose,
        channel=_otp_route(user=locked_user, purpose=purpose)[0],
        destination=_otp_route(user=locked_user, purpose=purpose)[1],
        expires_at=now + timedelta(seconds=settings.ACCOUNT_OTP_LIFETIME_SECONDS),
    )
    challenge.code_hash = _account_otp_code_hash(challenge.id, code)
    challenge.save(update_fields=["code_hash"])
    language = resolve_language(user=locked_user)
    with translation.override(language):
        subject, body = account_otp_message_content(challenge, code)
    NotificationDelivery.objects.create(
        account_challenge=challenge,
        kind=NotificationDelivery.Kind.ACCOUNT_OTP,
        channel=challenge.channel,
        destination=challenge.destination,
        language=language,
        subject=subject,
        body=body,
    )
    if settings.DEBUG:
        print(
            f"[IMMOLIB] OTP {challenge.purpose} envoye par {challenge.channel} "
            f"a {challenge.destination}: {code}"
        )
    return AccountOtpIssue(challenge=challenge, created=True, code=code)


@transaction.atomic
def register_user(*, data: RegisterUserData) -> RegistrationResult:
    """Crée un compte public et réserve son éventuelle invitation locataire."""

    phone = normalize_e164(data.phone)
    email = data.email.strip().lower() if data.email else ""
    if User.objects.filter(phone=phone).exists():
        raise ValidationError(
            {"phone": _("Un compte utilise déjà ce numéro de téléphone.")}
        )
    if email and User.objects.filter(email__iexact=email).exists():
        raise ValidationError(
            {"email": _("Un compte utilise déjà cette adresse email.")}
        )
    try:
        tenant_invitation = None
        if data.tenant_invitation_token:
            from modules.leases.services import (
                validate_tenant_invitation_registration,
            )

            tenant_invitation = validate_tenant_invitation_registration(
                token=data.tenant_invitation_token,
                phone=data.phone,
                email=data.email,
            )
        user = User.objects.create_user(
            phone=phone,
            password=data.password,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=email,
            phone_verified_at=None,
        )
        if tenant_invitation is not None:
            from modules.leases.services import reserve_tenant_invitation

            reserve_tenant_invitation(
                invitation=tenant_invitation,
                user=user,
            )
        if user.email:
            purpose = AccountOtpChallenge.Purpose.EMAIL_VERIFICATION
            verification_channel = AccountOtpChallenge.Channel.EMAIL
        else:
            purpose = AccountOtpChallenge.Purpose.PHONE_VERIFICATION
            verification_channel = AccountOtpChallenge.Channel.SMS
        otp_issue = issue_account_otp(user=user, purpose=purpose)
        return RegistrationResult(
            user=user,
            otp_issue=otp_issue,
            verification_channel=verification_channel,
        )
    except IntegrityError as exc:
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                {"email": _("Un compte utilise déjà cette adresse email.")}
            ) from exc
        raise ValidationError(
            {"phone": _("Un compte utilise déjà ce numéro de téléphone.")}
        ) from exc


def request_account_otp(*, phone: str, purpose: str) -> AccountOtpIssue | None:
    """Retourne None sans distinguer un compte absent d'un compte inéligible."""

    user = User.objects.filter(phone=normalize_e164(phone), is_active=True).first()
    if user is None:
        return None
    if purpose == AccountOtpChallenge.Purpose.PHONE_VERIFICATION:
        if user.phone_verified_at is not None:
            return None
    elif purpose == AccountOtpChallenge.Purpose.EMAIL_VERIFICATION:
        if not user.email or user.email_verified_at is not None:
            return None
    elif purpose == AccountOtpChallenge.Purpose.PASSWORD_RESET:
        if not user.has_verified_contact:
            return None
    else:
        raise ValueError(_("Finalité OTP inconnue."))
    return issue_account_otp(user=user, purpose=purpose)


def _consume_valid_account_otp(
    *, phone: str, purpose: str, code: str, on_success, now=None
):
    now = now or timezone.now()
    invalid = False
    result = None
    with transaction.atomic():
        challenge = (
            AccountOtpChallenge.objects.select_for_update()
            .select_related("user")
            .filter(
                user__phone=normalize_e164(phone),
                user__is_active=True,
                purpose=purpose,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            raise InvalidAccountOtp(INVALID_ACCOUNT_OTP_MESSAGE)
        if (
            challenge.expires_at <= now
            or challenge.attempts >= settings.ACCOUNT_OTP_MAX_ATTEMPTS
        ):
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
            invalid = True
        elif not challenge.code_hash or not compare_digest(
            challenge.code_hash, _account_otp_code_hash(challenge.id, code)
        ):
            challenge.attempts += 1
            update_fields = ["attempts"]
            if challenge.attempts >= settings.ACCOUNT_OTP_MAX_ATTEMPTS:
                challenge.consumed_at = now
                update_fields.append("consumed_at")
            challenge.save(update_fields=update_fields)
            invalid = True
        else:
            challenge.verified_at = now
            challenge.consumed_at = now
            challenge.save(update_fields=["verified_at", "consumed_at"])
            result = on_success(challenge)

    if invalid:
        raise InvalidAccountOtp(INVALID_ACCOUNT_OTP_MESSAGE)
    return result


def confirm_phone_verification(*, phone: str, code: str):
    def activate_account(challenge):
        user = challenge.user
        if user.phone_verified_at is None:
            user.phone_verified_at = challenge.verified_at
            user.save(update_fields=["phone_verified_at", "updated_at"])
        from modules.leases.models import Tenant

        Tenant.objects.filter(phone=user.phone).update(
            linked_user=user,
            status=Tenant.Status.ACTIVE,
            updated_at=timezone.now(),
        )
        from modules.properties.services import accept_pending_coowner_invitations
        from modules.leases.services import accept_pending_tenant_invitations

        accept_pending_coowner_invitations(user=user)
        accept_pending_tenant_invitations(user=user)
        return user

    return _consume_valid_account_otp(
        phone=phone,
        purpose=AccountOtpChallenge.Purpose.PHONE_VERIFICATION,
        code=code,
        on_success=activate_account,
    )


def confirm_email_verification(*, phone: str, code: str):
    def activate_account(challenge):
        user = challenge.user
        if user.email_verified_at is None:
            user.email_verified_at = challenge.verified_at
            user.save(update_fields=["email_verified_at", "updated_at"])
        from modules.leases.services import accept_pending_tenant_invitations

        accept_pending_tenant_invitations(user=user)
        return user

    return _consume_valid_account_otp(
        phone=phone,
        purpose=AccountOtpChallenge.Purpose.EMAIL_VERIFICATION,
        code=code,
        on_success=activate_account,
    )


def confirm_password_reset(*, phone: str, code: str, password: str):
    def change_password(challenge):
        user = challenge.user
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        from django.contrib.sessions.models import Session

        for session in Session.objects.all():
            try:
                if session.get_decoded().get("_auth_user_id") == str(user.id):
                    session.delete()
            except Exception:
                continue
        return user

    return _consume_valid_account_otp(
        phone=phone,
        purpose=AccountOtpChallenge.Purpose.PASSWORD_RESET,
        code=code,
        on_success=change_password,
    )
