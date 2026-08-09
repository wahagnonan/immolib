"""Défauts des plans. Les valeurs sont surchargeables par l'environnement
(voir config/settings.py) et restent modifiables ensuite dans la base via
l'administration Django (champs max_houses, price_monthly, features)."""

FREE_FEATURES = [
    "tenant_management",
    "lease_management",
    "payment_tracking",
    "receipt_generation",
    "receipt_verification",
    "basic_dashboard",
    "limited_notifications",
]

ESSENTIAL_FEATURES = FREE_FEATURES + [
    "improved_notifications",
    "payment_reminders",
    "payment_history",
    "co_owners",
    "basic_statistics",
]

PRO_FEATURES = ESSENTIAL_FEATURES + [
    "automated_notifications",
    "advanced_statistics",
    "unpaid_tracking",
    "data_export",
    "multi_user",
    "financial_reports",
]
