import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from modules.billing.models import RentCharge
from modules.leases.models import Tenant


class Payment(models.Model):
    """Somme declaree par un bailleur et conservee comme operation tracable."""

    class Method(models.TextChoices):
        CASH = "CASH", "Especes"
        BANK_TRANSFER = "BANK_TRANSFER", "Virement bancaire"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money confirmé"
        EXTERNAL_MOBILE_MONEY = "EXTERNAL_MOBILE_MONEY", "Mobile Money hors ImmoLib"
        SECURITY_DEPOSIT_APPLICATION = (
            "SECURITY_DEPOSIT_APPLICATION",
            "Caution affectée au loyer",
        )
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        RECORDED_BY_OWNER = "RECORDED_BY_OWNER", "Declare par le bailleur"
        CONFIRMED_BY_PROVIDER = (
            "CONFIRMED_BY_PROVIDER",
            "Confirmé par le prestataire",
        )
        CONFIRMED_BY_TENANT = "CONFIRMED_BY_TENANT", "Confirme par le locataire"
        DISPUTED_BY_TENANT = "DISPUTED_BY_TENANT", "Conteste par le locataire"
        CANCELLED = "CANCELLED", "Annule"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(
        "montant",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField("devise", max_length=3, default="XOF")
    method = models.CharField("moyen", max_length=32, choices=Method.choices)
    status = models.CharField(
        "statut",
        max_length=32,
        choices=Status.choices,
        default=Status.RECORDED_BY_OWNER,
    )
    received_at = models.DateTimeField("recu le", default=timezone.now)
    external_reference = models.CharField("reference externe", max_length=120, blank=True)
    note = models.TextField("note", blank=True)
    is_cash_movement = models.BooleanField(
        "mouvement de trésorerie",
        default=True,
        help_text="Faux lorsqu'une caution déjà encaissée est affectée à un loyer.",
    )
    idempotency_key = models.UUIDField("cle d'idempotence")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_payments",
        verbose_name="enregistre par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    rent_charges = models.ManyToManyField(
        RentCharge,
        through="PaymentAllocation",
        related_name="payments",
    )

    class Meta:
        ordering = ["-received_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recorded_by", "idempotency_key"],
                name="one_payment_per_recorder_idempotency_key",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "received_at"],
                name="payment_status_received_idx",
            )
        ]
        verbose_name = "paiement"
        verbose_name_plural = "paiements"

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} - {self.get_method_display()}"


class SecurityDepositMovement(models.Model):
    """Journal append-only de la libération d'une caution.

    Ces mouvements décrivent des décisions exécutées hors ImmoLib. La
    plateforme ne détient pas les fonds.
    """

    class Type(models.TextChoices):
        REFUND = "REFUND", "Remboursement"
        RETENTION = "RETENTION", "Retenue justifiée"
        APPLY_TO_RENT = "APPLY_TO_RENT", "Affectation au loyer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deposit_obligation = models.ForeignKey(
        RentCharge,
        on_delete=models.PROTECT,
        related_name="security_deposit_movements",
    )
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reason = models.TextField(blank=True)
    agreement_confirmed = models.BooleanField(default=False)
    agreement_reference = models.CharField(max_length=160, blank=True)
    target_rent_charge = models.ForeignKey(
        RentCharge,
        on_delete=models.PROTECT,
        related_name="received_deposit_movements",
        null=True,
        blank=True,
    )
    resulting_payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="security_deposit_movements",
        null=True,
        blank=True,
    )
    idempotency_key = models.UUIDField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="security_deposit_movements",
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "idempotency_key"],
                name="one_deposit_movement_per_actor_key",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="security_deposit_movement_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        movement_type="APPLY_TO_RENT",
                        target_rent_charge__isnull=False,
                        agreement_confirmed=True,
                    )
                    | Q(
                        movement_type__in=("REFUND", "RETENTION"),
                        target_rent_charge__isnull=True,
                    )
                ),
                name="deposit_movement_target_matches_type",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.deposit_obligation_id} - "
            f"{self.get_movement_type_display()}: {self.amount}"
        )


class PaymentAllocation(models.Model):
    """Part d'un paiement affectee a une echeance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name="paiement",
    )
    rent_charge = models.ForeignKey(
        RentCharge,
        on_delete=models.PROTECT,
        related_name="payment_allocations",
        verbose_name="echeance",
    )
    amount = models.DecimalField(
        "montant affecte",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "rent_charge"],
                name="one_allocation_per_payment_and_charge",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_allocation_amount_positive",
            ),
        ]
        verbose_name = "affectation de paiement"
        verbose_name_plural = "affectations de paiement"

    def __str__(self) -> str:
        return f"{self.payment_id} -> {self.rent_charge_id}: {self.amount}"


class PaymentEvent(models.Model):
    """Journal append-only des changements importants d'un paiement."""

    class Type(models.TextChoices):
        RECORDED = "RECORDED", "Paiement enregistre"
        PROVIDER_CONFIRMED = "PROVIDER_CONFIRMED", "Prestataire a confirme"
        TENANT_CONFIRMED = "TENANT_CONFIRMED", "Locataire a confirme"
        TENANT_DISPUTED = "TENANT_DISPUTED", "Locataire a conteste"
        CANCELLED = "CANCELLED", "Paiement annule"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name="paiement",
    )
    event_type = models.CharField("type", max_length=32, choices=Type.choices)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_events",
        verbose_name="utilisateur acteur",
    )
    actor_tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_events",
        verbose_name="locataire acteur",
    )
    reason = models.TextField("motif", blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "evenement de paiement"
        verbose_name_plural = "evenements de paiement"

    def __str__(self) -> str:
        return f"{self.payment_id} - {self.get_event_type_display()}"


class PaymentProviderEvent(models.Model):
    """Événement externe reçu et traité de façon idempotente."""

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Reçu"
        PROCESSED = "PROCESSED", "Traité"
        IGNORED = "IGNORED", "Ignoré"
        FAILED = "FAILED", "Échec"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=40)
    external_event_id = models.CharField(max_length=120)
    event_type = models.CharField(max_length=60)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    transaction_reference = models.CharField(max_length=120, blank=True)
    rent_charge_reference = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payload_digest = models.CharField(max_length=64)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="provider_events",
        null=True,
        blank=True,
    )
    failure_reason = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_event_id"],
                name="one_payment_provider_event",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "received_at"],
                name="payment_provider_status_idx",
            )
        ]
        verbose_name = "événement prestataire de paiement"
        verbose_name_plural = "événements prestataire de paiement"

    def __str__(self) -> str:
        return f"{self.provider} - {self.external_event_id}"
