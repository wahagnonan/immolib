import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager
from .phones import validate_e164


class User(AbstractUser):
    """Compte unique utilisable comme bailleur, coproprietaire ou locataire."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    phone = models.CharField(
        "telephone",
        max_length=20,
        unique=True,
        validators=[validate_e164],
    )
    email = models.EmailField("email", blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["phone"]

    def __str__(self) -> str:
        return self.get_full_name() or self.phone

    @property
    def has_verified_contact(self) -> bool:
        return self.phone_verified_at is not None or self.email_verified_at is not None


class AccountOtpChallenge(models.Model):
    """Code temporaire pour verifier un telephone ou reinitialiser un secret."""

    class Purpose(models.TextChoices):
        PHONE_VERIFICATION = "PHONE_VERIFICATION", "Verification du telephone"
        EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Verification de l'email"
        PASSWORD_RESET = "PASSWORD_RESET", "Reinitialisation du mot de passe"

    class Channel(models.TextChoices):
        SMS = "SMS", "SMS"
        EMAIL = "EMAIL", "Email"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="account_otp_challenges",
    )
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    channel = models.CharField(
        max_length=8, choices=Channel.choices, default=Channel.SMS
    )
    destination = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "purpose", "created_at"],
                name="account_otp_lookup_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.phone} - {self.get_purpose_display()}"
