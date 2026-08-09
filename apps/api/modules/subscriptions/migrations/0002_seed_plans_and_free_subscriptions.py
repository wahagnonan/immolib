from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.utils import timezone


PLANS = {
    "free": {
        "name": "Gratuit",
        "description": "Gestion locative essentielle pour démarrer.",
        "price_monthly": 0,
        "max_houses": 1,
        "features": [
            "tenant_management",
            "lease_management",
            "payment_tracking",
            "receipt_generation",
            "receipt_verification",
            "basic_dashboard",
            "limited_notifications",
        ],
    },
    "essential": {
        "name": "Essentiel",
        "description": "Notifications, rappels et copropriétaires.",
        "price_monthly": 2000,
        "max_houses": 5,
        "features": [
            "tenant_management",
            "lease_management",
            "payment_tracking",
            "receipt_generation",
            "receipt_verification",
            "basic_dashboard",
            "limited_notifications",
            "improved_notifications",
            "payment_reminders",
            "payment_history",
            "co_owners",
            "basic_statistics",
        ],
    },
    "pro": {
        "name": "Pro",
        "description": "Statistiques avancées, export et multi-utilisateurs.",
        "price_monthly": 4000,
        "max_houses": 15,
        "features": [
            "tenant_management",
            "lease_management",
            "payment_tracking",
            "receipt_generation",
            "receipt_verification",
            "basic_dashboard",
            "limited_notifications",
            "improved_notifications",
            "payment_reminders",
            "payment_history",
            "co_owners",
            "basic_statistics",
            "automated_notifications",
            "advanced_statistics",
            "unpaid_tracking",
            "data_export",
            "multi_user",
            "financial_reports",
        ],
    },
}


def seed_plans_and_backfill_free_subscriptions(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    Subscription = apps.get_model("subscriptions", "Subscription")
    User = apps.get_model("accounts", "User")

    plans = {}
    for slug, values in PLANS.items():
        plan, _ = SubscriptionPlan.objects.update_or_create(
            slug=slug,
            defaults={
                "name": values["name"],
                "description": values["description"],
                "price_monthly": values["price_monthly"],
                "currency": "XOF",
                "max_houses": values["max_houses"],
                "features": values["features"],
                "is_active": True,
            },
        )
        plans[slug] = plan

    # Les utilisateurs existants reçoivent automatiquement le plan Gratuit.
    # Aucune donnée existante (maisons, locataires, paiements...) n'est
    # supprimée : seul le quota de nouvelles créations sera appliqué.
    free_plan = plans["free"]
    now = timezone.now()
    for user in User.objects.all().iterator():
        Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": free_plan,
                "status": "ACTIVE",
                "started_at": now,
                "expires_at": now + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS),
            },
        )


def reverse_seed(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    Subscription = apps.get_model("subscriptions", "Subscription")
    Subscription.objects.all().delete()
    SubscriptionPlan.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_plans_and_backfill_free_subscriptions,
            reverse_code=reverse_seed,
        ),
    ]
