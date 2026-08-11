import os
from pathlib import Path

from modules.i18n.languages import LANGUAGES


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
if DEBUG is False and SECRET_KEY == "unsafe-local-development-key":
    raise RuntimeError("DJANGO_SECRET_KEY est obligatoire en dehors du mode DEBUG.")
IS_PRODUCTION = os.getenv("DJANGO_IS_PRODUCTION", "false").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "modules.i18n",
    "modules.accounts",
    "modules.properties",
    "modules.leases",
    "modules.billing",
    "modules.documents",
    "modules.notifications",
    "modules.tenant_portal",
    "modules.maintenance",
    "modules.payments",
    "modules.subscriptions",
    "modules.admin_panel",
    "modules.whatsapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "modules.i18n.middleware.ImmoLocaleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("DATABASE_ENGINE", "sqlite") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "immolib"),
            "USER": os.getenv("POSTGRES_USER", "immolib"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "immolib"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGES = LANGUAGES
LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "immolib_language"

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:3000").rstrip("/")
CSRF_TRUSTED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "DJANGO_CSRF_TRUSTED_ORIGINS", PUBLIC_APP_URL
    ).split(",")
    if origin.strip()
)
EXPOSE_TEST_OTP = os.getenv("EXPOSE_TEST_OTP", "false").lower() == "true"
if EXPOSE_TEST_OTP and not DEBUG:
    raise RuntimeError("EXPOSE_TEST_OTP doit rester désactivé en dehors du mode DEBUG.")
ACCOUNT_OTP_LIFETIME_SECONDS = int(
    os.getenv("IMMOLIB_ACCOUNT_OTP_LIFETIME_SECONDS", "600")
)
ACCOUNT_OTP_COOLDOWN_SECONDS = int(
    os.getenv("IMMOLIB_ACCOUNT_OTP_COOLDOWN_SECONDS", "60")
)
ACCOUNT_OTP_MAX_ATTEMPTS = int(os.getenv("IMMOLIB_ACCOUNT_OTP_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MAX_ATTEMPTS = int(
    os.getenv("IMMOLIB_LOGIN_LOCKOUT_MAX_ATTEMPTS", "10")
)
LOGIN_LOCKOUT_WINDOW_SECONDS = int(
    os.getenv("IMMOLIB_LOGIN_LOCKOUT_WINDOW_SECONDS", "900")
)
LOGIN_LOCKOUT_DURATION_SECONDS = int(
    os.getenv("IMMOLIB_LOGIN_LOCKOUT_DURATION_SECONDS", "300")
)
DOCUMENT_OTP_COOLDOWN_SECONDS = int(
    os.getenv("IMMOLIB_DOCUMENT_OTP_COOLDOWN_SECONDS", "60")
)
TENANT_INVITATION_LIFETIME_DAYS = int(
    os.getenv("IMMOLIB_TENANT_INVITATION_LIFETIME_DAYS", "14")
)

# Chaque canal utilise un adaptateur interchangeable. En developpement, un
# adaptateur simule par defaut les envois afin que les codes OTP restent
# accessibles sans configuration SMTP/SMS externe.
SIMULATED_ADAPTER = "modules.documents.notifications.SimulatedNotificationAdapter"
NOTIFICATION_ADAPTERS = {
    "SMS": os.getenv(
        "IMMOLIB_SMS_NOTIFICATION_ADAPTER",
        SIMULATED_ADAPTER if DEBUG else "",
    ),
    "EMAIL": os.getenv(
        "IMMOLIB_EMAIL_NOTIFICATION_ADAPTER",
        SIMULATED_ADAPTER if DEBUG else "",
    ),
    "WHATSAPP": os.getenv(
        "IMMOLIB_WHATSAPP_NOTIFICATION_ADAPTER",
        SIMULATED_ADAPTER if DEBUG else "",
    ),
    "PUSH": os.getenv(
        "IMMOLIB_PUSH_NOTIFICATION_ADAPTER",
        SIMULATED_ADAPTER if DEBUG else "",
    ),
}
# WhatsApp Business Cloud API. WHATSAPP_WEBHOOK_VERIFY_TOKEN est le secret
# saisi dans le dashboard Meta (champ "Vérifier le token") ; le handshake GET
# ne réussit que s'il correspond. L'adaptateur d'envoi n'est actif que lorsque
# WHATSAPP_ACCESS_TOKEN et WHATSAPP_PHONE_NUMBER_ID sont renseignés.
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v24.0")
WHATSAPP_GRAPH_BASE_URL = os.getenv(
    "WHATSAPP_GRAPH_BASE_URL", "https://graph.facebook.com"
)

NOTIFICATION_MAX_ATTEMPTS = int(os.getenv("IMMOLIB_NOTIFICATION_MAX_ATTEMPTS", "3"))
NOTIFICATION_RETRY_SECONDS = int(os.getenv("IMMOLIB_NOTIFICATION_RETRY_SECONDS", "60"))
NOTIFICATION_PROCESSING_TIMEOUT_SECONDS = int(
    os.getenv("IMMOLIB_NOTIFICATION_PROCESSING_TIMEOUT_SECONDS", "300")
)
RENT_REMINDER_OFFSETS_DAYS = tuple(
    int(value.strip())
    for value in os.getenv("IMMOLIB_RENT_REMINDER_OFFSETS_DAYS", "-3,0,3,7").split(",")
    if value.strip()
)
RENT_REMINDER_CHANNELS = tuple(
    value.strip().upper()
    for value in os.getenv("IMMOLIB_RENT_REMINDER_CHANNELS", "AUTO").split(",")
    if value.strip()
)

# Amazon SES. Les identifiants AWS sont fournis par la chaîne standard boto3
# (variables d'environnement, profil ou rôle d'instance), jamais dans le code.
AWS_SES_REGION = os.getenv("AWS_SES_REGION", "af-south-1")
AWS_SES_FROM_EMAIL = os.getenv("AWS_SES_FROM_EMAIL", "")

# Firebase Admin peut utiliser Application Default Credentials ou un fichier
# de compte de service monté en dehors du dépôt.
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
FIREBASE_CREDENTIALS_FILE = os.getenv("FIREBASE_CREDENTIALS_FILE", "")

# Passerelle de référence pour les webhooks Mobile Money. Le secret doit être
# fourni hors du dépôt et remplacé par l'adaptateur du PSP choisi.
MOBILE_MONEY_WEBHOOK_SECRET = os.getenv("MOBILE_MONEY_WEBHOOK_SECRET", "")
MOBILE_MONEY_WEBHOOK_TOLERANCE_SECONDS = int(
    os.getenv("MOBILE_MONEY_WEBHOOK_TOLERANCE_SECONDS", "300")
)

# Abonnements ImmoLib : plans, limites et paiement PayDunya.
SUBSCRIPTION_CURRENCY = os.getenv("SUBSCRIPTION_CURRENCY", "XOF")
SUBSCRIPTION_DURATION_DAYS = int(
    os.getenv("SUBSCRIPTION_DURATION_DAYS", "30")
)
SUBSCRIPTION_PLAN_DEFAULTS = {
    "free": {
        "name": "Gratuit",
        "description": "Gestion locative essentielle pour démarrer.",
        "price_monthly": 0,
        "max_houses": int(os.getenv("FREE_MAX_HOUSES", "1")),
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
        "price_monthly": int(os.getenv("ESSENTIAL_PRICE", "2000")),
        "max_houses": int(os.getenv("ESSENTIAL_MAX_HOUSES", "5")),
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
        "price_monthly": int(os.getenv("PRO_PRICE", "4000")),
        "max_houses": int(os.getenv("PRO_MAX_HOUSES", "15")),
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

# PayDunya (agrégateur mobile money / cartes). En l'absence de clés, les plans
# payants s'activent immédiatement en mode pilote avec transaction tracée.
PAYDUNYA_MASTER_KEY = os.getenv("PAYDUNYA_MASTER_KEY", "")
PAYDUNYA_PRIVATE_KEY = os.getenv("PAYDUNYA_PRIVATE_KEY", "")
PAYDUNYA_PUBLIC_KEY = os.getenv("PAYDUNYA_PUBLIC_KEY", "")
PAYDUNYA_TOKEN = os.getenv("PAYDUNYA_TOKEN", "")
PAYDUNYA_MODE = os.getenv("PAYDUNYA_MODE", "test")
# Le mode pilote (activation immédiate sans paiement) n’est autorisé qu’en
# développement ou lorsqu’il est explicitement activé en production.
SUBSCRIPTIONS_PILOT_MODE = (
    os.getenv("IMMOLIB_SUBSCRIPTIONS_PILOT_MODE", "false").lower() == "true"
)
PAYDUNYA_STORE_NAME = os.getenv("PAYDUNYA_STORE_NAME", "ImmoLib")
PAYDUNYA_CALLBACK_URL = os.getenv(
    "PAYDUNYA_CALLBACK_URL",
    f"{PUBLIC_APP_URL}/backend/api/v1/webhooks/paydunya/",
)

# Les sessions restent dans un cookie HttpOnly. Le cookie CSRF doit rester lisible
# par le frontend afin d'envoyer l'en-tete X-CSRFToken sur les requetes d'ecriture.
COOKIE_SECURE = os.getenv("DJANGO_COOKIE_SECURE", str(not DEBUG)).lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = COOKIE_SECURE
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(
    os.getenv("DJANGO_SESSION_COOKIE_AGE_SECONDS", "604800")
)
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}
