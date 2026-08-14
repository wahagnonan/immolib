import uuid
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from modules.leases.models import Lease


class RentCharge(models.Model):
    """Obligation financière d'un bail.

    Le nom historique ``RentCharge`` reste utilisé pour préserver l'API
    existante. ``charge_type`` permet maintenant de distinguer un loyer d'une
    caution sans créer un second moteur financier.
    """

    class Type(models.TextChoices):
        RENT = "RENT", _("Loyer")
        SECURITY_DEPOSIT = "SECURITY_DEPOSIT", _("Caution")

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", _("A venir")
        DUE = "DUE", _("A payer")
        PARTIALLY_PAID = "PARTIALLY_PAID", _("Partiellement payee")
        PAID = "PAID", _("Payee")
        OVERDUE = "OVERDUE", _("En retard")
        DISPUTED = "DISPUTED", _("Contestee")
        CANCELLED = "CANCELLED", _("Annulee")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    charge_type = models.CharField(
        "type d'obligation",
        max_length=24,
        choices=Type.choices,
        default=Type.RENT,
    )
    lease = models.ForeignKey(
        Lease,
        on_delete=models.PROTECT,
        related_name="rent_charges",
        verbose_name="bail",
    )
    period_start = models.DateField("debut de periode")
    period_end = models.DateField("fin de periode")
    due_date = models.DateField("date limite")
    rent_amount = models.DecimalField(
        "loyer",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    charges_amount = models.DecimalField(
        "charges",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    amount_due = models.DecimalField(
        "total attendu",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    amount_paid = models.DecimalField(
        "total paye",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    amount_released = models.DecimalField(
        _("caution libérée"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text=(
            _("Montant remboursé, retenu ou affecté. "
            "ImmoLib ne conserve pas les fonds.")
        ),
    )
    currency = models.CharField("devise", max_length=3, default="XOF")
    status = models.CharField(
        "statut", max_length=24, choices=Status.choices, default=Status.UPCOMING
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "lease"]
        constraints = [
            models.UniqueConstraint(
                fields=["lease", "charge_type", "period_start"],
                name="one_obligation_per_lease_type_period",
            ),
            models.UniqueConstraint(
                fields=["lease"],
                condition=Q(charge_type="SECURITY_DEPOSIT"),
                name="one_security_deposit_obligation_per_lease",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="rent_charge_period_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(due_date__gte=models.F("period_start"))
                & Q(due_date__lte=models.F("period_end")),
                name="obligation_due_date_inside_period",
            ),
            models.CheckConstraint(
                condition=Q(amount_due__gt=0),
                name="rent_charge_amount_due_positive",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0) & Q(amount_paid__lte=models.F("amount_due")),
                name="rent_charge_paid_between_zero_and_due",
            ),
            models.CheckConstraint(
                condition=Q(amount_released__gte=0)
                & Q(amount_released__lte=models.F("amount_paid")),
                name="deposit_released_between_zero_and_paid",
            ),
        ]
        verbose_name = _("echeance de loyer")
        verbose_name_plural = _("echeances de loyer")
        indexes = [
            models.Index(
                fields=["charge_type", "status", "period_start"],
                name="obligation_type_status_idx",
            ),
            models.Index(
                fields=["lease", "charge_type", "status"],
                name="obligation_lease_type_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.period_start and self.period_start.day != 1:
            raise ValidationError(
                {"period_start": _("La periode doit commencer le premier du mois.")}
            )
        if (
            self.charge_type == self.Type.RENT
            and self.rent_amount is not None
            and self.charges_amount is not None
        ):
            expected_total = self.rent_amount + self.charges_amount
            if self.amount_due != expected_total:
                raise ValidationError(
                    {"amount_due": _("Le total doit etre egal au loyer plus les charges.")}
                )
        if self.charge_type == self.Type.SECURITY_DEPOSIT:
            if self.rent_amount != 0 or self.charges_amount != 0:
                raise ValidationError(
                    _("Une caution ne doit pas être comptabilisée comme un loyer.")
                )
        elif self.amount_released:
            raise ValidationError(
                {"amount_released": _("Seule une caution peut être libérée.")}
            )

        if (
            self.amount_paid is not None
            and self.amount_due is not None
            and self.amount_paid > self.amount_due
        ):
            raise ValidationError(
                {"amount_paid": _("Le total paye ne peut pas depasser le total attendu.")}
            )

    @property
    def period_label(self) -> str:
        return self.period_start.strftime("%Y-%m")

    @property
    def obligation_label(self) -> str:
        if self.charge_type == self.Type.SECURITY_DEPOSIT:
            return "Caution"
        return f"Loyer {self.period_label}"

    @property
    def balance_due(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def held_balance(self) -> Decimal:
        if self.charge_type != self.Type.SECURITY_DEPOSIT:
            return Decimal("0")
        return self.amount_paid - self.amount_released

    @property
    def deposit_state(self) -> str:
        if self.charge_type != self.Type.SECURITY_DEPOSIT:
            return ""
        if self.amount_paid == 0:
            return "EXPECTED"
        if self.amount_paid < self.amount_due and self.amount_released == 0:
            return "PARTIALLY_HELD"
        if self.amount_released == 0:
            return "HELD"
        if self.held_balance > 0:
            return "PARTIALLY_SETTLED"
        return "SETTLED"

    def __str__(self) -> str:
        return f"{self.lease} - {self.obligation_label}"
