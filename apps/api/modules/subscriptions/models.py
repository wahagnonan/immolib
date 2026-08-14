import uuid

from django.conf import settings
from django.db import models


class Plan(models.Model):
    """Plan d'abonnement ImmoLib."""

    class Interval(models.TextChoices):
        MONTHLY = "MONTHLY", "Mensuel"
        YEARLY = "YEARLY", "Annuel"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=0)  # FCFA, pas de centimes
    currency = models.CharField(max_length=3, default="XOF")
    interval = models.CharField(
        max_length=12, choices=Interval.choices, default=Interval.MONTHLY
    )
    max_houses = models.PositiveIntegerField(default=1)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    is_highlighted = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "price"]

    def __str__(self) -> str:
        return f"{self.name} — {self.price} {self.currency}/{self.get_interval_display()}"


class Subscription(models.Model):
    """Abonnement d'un utilisateur à un plan."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        PENDING = "PENDING", "En attente"
        CANCELLED = "CANCELLED", "Annulé"
        EXPIRED = "EXPIRED", "Expiré"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    paydunya_token = models.CharField(max_length=200, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.plan.name} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def max_houses(self) -> int:
        return self.plan.max_houses


class SubscriptionPayment(models.Model):
    """Historique des paiements d'abonnement via PayDunya."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        COMPLETED = "COMPLETED", "Complété"
        FAILED = "FAILED", "Échoué"
        CANCELLED = "CANCELLED", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    paydunya_token = models.CharField(max_length=200, blank=True)
    paydunya_invoice_token = models.CharField(max_length=200, blank=True)
    payment_url = models.URLField(blank=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Paiement {self.amount} {self.currency} — {self.status}"
