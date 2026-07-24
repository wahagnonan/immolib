import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
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
    "modules.accounts",
    "modules.properties",
    "modules.leases",
    "modules.billing",
    "modules.payments",
    "modules.documents",
    "modules.notifications",
    "modules.tenant_portal",
    "modules.maintenance",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

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
ACCOUNT_OTP_LIFETIME_SECONDS = int(
    os.getenv("IMMOLIB_ACCOUNT_OTP_LIFETIME_SECONDS", "600")
)
ACCOUNT_OTP_COOLDOWN_SECONDS = int(
    os.getenv("IMMOLIB_ACCOUNT_OTP_COOLDOWN_SECONDS", "60")
)
ACCOUNT_OTP_MAX_ATTEMPTS = int(os.getenv("IMMOLIB_ACCOUNT_OTP_MAX_ATTEMPTS", "5"))
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

# Les sessions restent dans un cookie HttpOnly. Le cookie CSRF doit rester lisible
# par le frontend afin d'envoyer l'en-tete X-CSRFToken sur les requetes d'ecriture.
COOKIE_SECURE = os.getenv("DJANGO_COOKIE_SECURE", str(not DEBUG)).lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = COOKIE_SECURE
SESSION_COOKIE_SAMESITE = "Lax"
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
