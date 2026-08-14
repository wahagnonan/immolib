import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Plan, Subscription, SubscriptionPayment


def get_paydunya_config() -> dict:
    """Retourne la configuration PayDunya depuis les variables d'environnement."""
    return {
        "PAYDUNYA-MASTER-KEY": getattr(settings, "PAYDUNYA_MASTER_KEY", ""),
        "PAYDUNYA-PRIVATE-KEY": getattr(settings, "PAYDUNYA_PRIVATE_KEY", ""),
        "PAYDUNYA-TOKEN": getattr(settings, "PAYDUNYA_TOKEN", ""),
    }


def verify_paydunya_hash(master_key: str, received_hash: str) -> bool:
    """Vérifie que le hash reçu vient bien de PayDunya."""
    computed = hashlib.sha512(master_key.encode()).hexdigest()
    return computed == received_hash


def get_or_create_active_plan() -> Plan:
    """Retourne ou crée le plan gratuit par défaut."""
    plan, _ = Plan.objects.get_or_create(
        slug="decouverte",
        defaults={
            "name": "Découverte",
            "description": "Pour tester ImmoLib sur une première location.",
            "price": 0,
            "max_houses": 1,
            "features": [
                "Loyers, cautions et avances",
                "Documents vérifiables",
                "Partage manuel",
            ],
            "is_active": True,
            "display_order": 0,
        },
    )
    return plan


def get_user_subscription(user) -> Subscription:
    """Retourne l'abonnement actif d'un utilisateur, ou le plan gratuit."""
    subscription = Subscription.objects.filter(
        user=user, status=Subscription.Status.ACTIVE
    ).select_related("plan").first()

    if subscription and subscription.is_active:
        return subscription

    # Pas d'abonnement actif : créer un abonnement gratuit
    free_plan = get_or_create_active_plan()
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        plan=free_plan,
        defaults={
            "status": Subscription.Status.ACTIVE,
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=365 * 10),  # Illimité
        },
    )
    return subscription


def can_create_house(user) -> bool:
    """Vérifie si l'utilisateur peut créer une nouvelle maison."""
    subscription = get_user_subscription(user)
    from modules.properties.models import Property

    house_count = Property.objects.filter(ownerships__user=user).count()
    return house_count < subscription.max_houses


@transaction.atomic
def initiate_subscription_payment(user, plan_id: str) -> SubscriptionPayment:
    """Crée un paiement PayDunya pour un abonnement."""
    plan = Plan.objects.get(id=plan_id, is_active=True)
    public_url = getattr(settings, "PUBLIC_APP_URL", "http://localhost:3000")

    # Créer ou mettre à jour l'abonnement
    subscription, _ = Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": Subscription.Status.PENDING,
        },
    )

    # Créer le paiement
    payment = SubscriptionPayment.objects.create(
        subscription=subscription,
        amount=plan.price,
        currency=plan.currency,
    )

    # Initialiser PayDunya
    import paydunya
    from paydunya import InvoiceItem, Store

    config = get_paydunya_config()
    paydunya.debug = getattr(settings, "DEBUG", False)
    paydunya.api_keys = config

    store = Store(
        name="ImmoLib",
        tagline="Gestion locative pour maisons",
        website_url=public_url,
    )

    items = [
        InvoiceItem(
            name=f"Abonnement ImmoLib — {plan.name}",
            quantity=1,
            unit_price=str(int(plan.price)),
            total_price=str(int(plan.price)),
            description=f"Abonnement {plan.get_interval_display().lower()} — {plan.max_houses} maison(s) max",
        )
    ]

    invoice = paydunya.Invoice(store)
    invoice.add_items(items)
    invoice.total_amount = int(plan.price)
    invoice.description = f"Abonnement {plan.name} — ImmoLib"

    # URLs de callback
    invoice.callback_url = f"{public_url}/api/v1/webhooks/paydunya/"
    invoice.return_url = f"{public_url}/abonnement?status=success"
    invoice.cancel_url = f"{public_url}/abonnement?status=cancelled"

    # Données personnalisées
    invoice.add_custom_data([
        ("user_id", str(user.id)),
        ("subscription_id", str(subscription.id)),
        ("payment_id", str(payment.id)),
    ])

    successful, response = invoice.create()

    if successful:
        payment.paydunya_invoice_token = response.get("invoice", {}).get("token", "")
        payment.payment_url = response.get("response_text", "")
        payment.save(update_fields=["paydunya_invoice_token", "payment_url"])
        return payment
    else:
        raise ValueError(f"Erreur PayDunya: {response}")


@transaction.atomic
def confirm_paydunya_payment(token: str) -> SubscriptionPayment:
    """Confirme un paiement PayDunya et active l'abonnement."""
    import paydunya
    from paydunya import Store

    config = get_paydunya_config()
    paydunya.debug = getattr(settings, "DEBUG", False)
    paydunya.api_keys = config

    store = Store(name="ImmoLib")
    invoice = paydunya.Invoice(store)

    successful, response = invoice.confirm(token)

    if not successful:
        raise ValueError("Paiement non confirmé par PayDunya")

    # Vérifier le hash
    master_key = config["PAYDUNYA-MASTER-KEY"]
    received_hash = response.get("data", {}).get("hash", "")
    if not verify_paydunya_hash(master_key, received_hash):
        raise ValueError("Hash PayDunya invalide")

    status = response.get("data", {}).get("status", "")
    if status != "completed":
        raise ValueError(f"Paiement non complété: {status}")

    # Trouver le paiement
    payment_id = response.get("data", {}).get("custom_data", {}).get("payment_id", "")
    payment = SubscriptionPayment.objects.get(id=payment_id)

    # Mettre à jour le paiement
    payment.status = SubscriptionPayment.Status.COMPLETED
    payment.paydunya_token = token
    payment.customer_name = response.get("data", {}).get("customer", {}).get("name", "")
    payment.customer_email = response.get("data", {}).get("customer", {}).get("email", "")
    payment.customer_phone = response.get("data", {}).get("customer", {}).get("phone", "")
    payment.paid_at = timezone.now()
    payment.save()

    # Activer l'abonnement
    subscription = payment.subscription
    subscription.status = Subscription.Status.ACTIVE
    subscription.paydunya_token = token
    subscription.current_period_start = timezone.now()

    if subscription.plan.interval == Plan.Interval.MONTHLY:
        subscription.current_period_end = timezone.now() + timedelta(days=30)
    else:
        subscription.current_period_end = timezone.now() + timedelta(days=365)

    subscription.save()

    return payment
