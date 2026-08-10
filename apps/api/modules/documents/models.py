import uuid
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from modules.billing.models import RentCharge
from modules.payments.models import Payment, SecurityDepositMovement


class RentalDocument(models.Model):
    """Instantane verifiable d'un recu ou d'une quittance."""

    class Type(models.TextChoices):
        PAYMENT_RECEIPT = "PAYMENT_RECEIPT", _("Recu de paiement")
        RENT_RECEIPT = "RENT_RECEIPT", _("Quittance de loyer")
        DEPOSIT_RECEIPT = "DEPOSIT_RECEIPT", _("Reçu de caution")
        DEPOSIT_SETTLEMENT = "DEPOSIT_SETTLEMENT", _("Relevé de caution")

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Actif")
        VOIDED = "VOIDED", _("Invalide")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField("reference", max_length=40, unique=True)
    document_type = models.CharField("type", max_length=24, choices=Type.choices)
    status = models.CharField(
        "statut", max_length=12, choices=Status.choices, default=Status.ACTIVE
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="rental_documents",
        null=True,
        blank=True,
        verbose_name="paiement",
    )
    deposit_movement = models.ForeignKey(
        SecurityDepositMovement,
        on_delete=models.PROTECT,
        related_name="rental_documents",
        null=True,
        blank=True,
        verbose_name="mouvement de caution",
    )
    rent_charge = models.ForeignKey(
        RentCharge,
        on_delete=models.PROTECT,
        related_name="rental_documents",
        verbose_name="echeance",
    )
    amount = models.DecimalField(
        "montant documente",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField("devise", max_length=3)
    period_start = models.DateField("debut de periode")
    period_end = models.DateField("fin de periode")
    payment_method = models.CharField("moyen de paiement", max_length=64, blank=True)
    breakdown = models.JSONField("détail des affectations", default=list, blank=True)
    house_name = models.CharField("maison", max_length=120)
    house_address = models.CharField("adresse de la maison", max_length=255)
    tenant_name = models.CharField("locataire", max_length=160)
    tenant_phone = models.CharField("telephone du locataire", max_length=20)
    tenant_email = models.EmailField("email du locataire", blank=True)
    owner_name = models.CharField("bailleur", max_length=160)
    owner_phone = models.CharField("telephone du bailleur", max_length=20)
    issued_at = models.DateTimeField(auto_now_add=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "document_type"],
                condition=Q(status="ACTIVE", document_type="PAYMENT_RECEIPT"),
                name="one_active_receipt_per_payment",
            ),
            models.UniqueConstraint(
                fields=["rent_charge", "document_type"],
                condition=Q(status="ACTIVE", document_type="RENT_RECEIPT"),
                name="one_active_rent_receipt_per_charge",
            ),
            models.UniqueConstraint(
                fields=["rent_charge", "document_type"],
                condition=Q(status="ACTIVE", document_type="DEPOSIT_RECEIPT"),
                name="one_active_deposit_receipt_per_obligation",
            ),
            models.UniqueConstraint(
                fields=["deposit_movement", "document_type"],
                condition=Q(
                    status="ACTIVE",
                    document_type="DEPOSIT_SETTLEMENT",
                ),
                name="one_active_deposit_settlement_per_movement",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="rental_document_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "issued_at"],
                name="rental_doc_status_issued_idx",
            )
        ]
        verbose_name = _("document locatif")
        verbose_name_plural = _("documents locatifs")

    def __str__(self) -> str:
        return f"{self.reference} - {self.get_document_type_display()}"


class DocumentAccessLink(models.Model):
    """Lien revocable; son jeton est signe et n'est pas stocke en clair."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        RentalDocument,
        on_delete=models.PROTECT,
        related_name="access_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_links",
    )
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class OtpChallenge(models.Model):
    """Verification courte avant de donner acces au document."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_link = models.ForeignKey(
        DocumentAccessLink,
        on_delete=models.PROTECT,
        related_name="otp_challenges",
    )
    channel = models.CharField(max_length=16)
    destination = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    code_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]


class NotificationDelivery(models.Model):
    """Message a remettre plus tard à un adaptateur de canal."""

    class Kind(models.TextChoices):
        DOCUMENT_LINK = "DOCUMENT_LINK", _("Lien du document")
        OTP = "OTP", _("Code d'acces au document")
        ACCOUNT_OTP = "ACCOUNT_OTP", _("Code de verification du compte")
        RENT_REMINDER = "RENT_REMINDER", _("Rappel de loyer")
        TENANT_INVITATION = "TENANT_INVITATION", _("Invitation du locataire")
        PAYMENT_REQUEST = "PAYMENT_REQUEST", _("Paiement à confirmer")
        PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED", _("Paiement confirmé")

    class Channel(models.TextChoices):
        SMS = "SMS", _("SMS")
        EMAIL = "EMAIL", _("Email")
        WHATSAPP = "WHATSAPP", _("WhatsApp")
        PUSH = "PUSH", _("Notification push")

    class Status(models.TextChoices):
        QUEUED = "QUEUED", _("En attente")
        PROCESSING = "PROCESSING", _("Traitement en cours")
        SENT = "SENT", _("Envoye")
        FAILED = "FAILED", _("Echec")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_link = models.ForeignKey(
        DocumentAccessLink,
        on_delete=models.PROTECT,
        related_name="deliveries",
        null=True,
        blank=True,
    )
    otp_challenge = models.ForeignKey(
        OtpChallenge,
        on_delete=models.PROTECT,
        related_name="deliveries",
        null=True,
        blank=True,
    )
    account_challenge = models.ForeignKey(
        "accounts.AccountOtpChallenge",
        on_delete=models.PROTECT,
        related_name="deliveries",
        null=True,
        blank=True,
    )
    rent_charge = models.ForeignKey(
        RentCharge,
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
        null=True,
        blank=True,
    )
    tenant_invitation = models.ForeignKey(
        "leases.TenantInvitation",
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
        null=True,
        blank=True,
    )
    payment_request = models.ForeignKey(
        "payments.PaymentRequest",
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
        null=True,
        blank=True,
    )
    scheduled_for = models.DateField(null=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    destination = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    language = models.CharField(
        "langue du destinataire",
        max_length=10,
        blank=True,
        default="",
        help_text="Langue figee a la mise en file ; le worker est asynchrone.",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.QUEUED
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at", "created_at"],
                name="notification_queue_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["access_link", "channel"],
                condition=Q(kind="DOCUMENT_LINK"),
                name="one_document_link_delivery_per_channel",
            ),
            models.UniqueConstraint(
                fields=["otp_challenge", "channel"],
                condition=Q(kind="OTP"),
                name="one_otp_delivery_per_challenge_channel",
            ),
            models.UniqueConstraint(
                fields=["account_challenge", "channel"],
                condition=Q(kind="ACCOUNT_OTP"),
                name="one_account_otp_delivery_per_channel",
            ),
            models.UniqueConstraint(
                fields=["rent_charge", "channel", "scheduled_for"],
                condition=Q(kind="RENT_REMINDER"),
                name="one_rent_reminder_per_charge_channel_date",
            ),
            models.UniqueConstraint(
                fields=["tenant_invitation", "channel"],
                condition=Q(kind="TENANT_INVITATION"),
                name="one_tenant_invitation_delivery_per_channel",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="DOCUMENT_LINK",
                        access_link__isnull=False,
                        otp_challenge__isnull=True,
                        account_challenge__isnull=True,
                        rent_charge__isnull=True,
                        tenant_invitation__isnull=True,
                        payment_request__isnull=True,
                        scheduled_for__isnull=True,
                    )
                    | Q(
                        kind="OTP",
                        access_link__isnull=False,
                        otp_challenge__isnull=False,
                        account_challenge__isnull=True,
                        rent_charge__isnull=True,
                        tenant_invitation__isnull=True,
                        payment_request__isnull=True,
                        scheduled_for__isnull=True,
                    )
                    | Q(
                        kind="ACCOUNT_OTP",
                        access_link__isnull=True,
                        otp_challenge__isnull=True,
                        account_challenge__isnull=False,
                        rent_charge__isnull=True,
                        tenant_invitation__isnull=True,
                        payment_request__isnull=True,
                        scheduled_for__isnull=True,
                    )
                    | Q(
                        kind="RENT_REMINDER",
                        access_link__isnull=True,
                        otp_challenge__isnull=True,
                        account_challenge__isnull=True,
                        rent_charge__isnull=False,
                        tenant_invitation__isnull=True,
                        payment_request__isnull=True,
                        scheduled_for__isnull=False,
                    )
                    | Q(
                        kind="TENANT_INVITATION",
                        access_link__isnull=True,
                        otp_challenge__isnull=True,
                        account_challenge__isnull=True,
                        rent_charge__isnull=True,
                        tenant_invitation__isnull=False,
                        payment_request__isnull=True,
                        scheduled_for__isnull=True,
                    )
                    | Q(
                        kind__in=("PAYMENT_REQUEST", "PAYMENT_CONFIRMED"),
                        access_link__isnull=True,
                        otp_challenge__isnull=True,
                        account_challenge__isnull=True,
                        rent_charge__isnull=False,
                        tenant_invitation__isnull=True,
                        payment_request__isnull=False,
                        scheduled_for__isnull=True,
                    )
                ),
                name="notification_delivery_source_matches_kind",
            ),
        ]


class ManualShareEvent(models.Model):
    """Préparation tracée d'un partage réalisé depuis l'appareil du bailleur."""

    class Channel(models.TextChoices):
        WHATSAPP = "WHATSAPP", _("WhatsApp")
        EMAIL = "EMAIL", _("Email")
        SMS = "SMS", _("SMS")
        NATIVE = "NATIVE", _("Partage de l'appareil")
        COPY = "COPY", _("Copie du lien")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        RentalDocument,
        on_delete=models.PROTECT,
        related_name="manual_share_events",
    )
    access_link = models.ForeignKey(
        DocumentAccessLink,
        on_delete=models.PROTECT,
        related_name="manual_share_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="manual_share_events",
    )
    channel = models.CharField(max_length=12, choices=Channel.choices)
    destination = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.document.reference} - {self.get_channel_display()}"
