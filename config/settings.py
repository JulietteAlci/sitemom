"""Django settings for the premium gold wedding band shop."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); real env vars take precedence."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return env(key, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def env_list(key, default=""):
    return [item.strip() for item in env(key, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DEBUG is off.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")
SITE_NAME = env("SITE_NAME", "Maison Alliance")
# Contact shown on product pages ("besoin de ce bijou en urgence ?") — leave empty to hide.
SITE_PHONE = env("SITE_PHONE", "")
SITE_WHATSAPP = env("SITE_WHATSAPP", "")
SITE_EMAIL = env("SITE_EMAIL", "")
# Return / withdrawal period shown on product pages (14 days = legal minimum in France).
RETURN_DAYS = int(env("RETURN_DAYS", "14"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "apps.core",
    "apps.pricing",
    "apps.catalog",
    "apps.blog",
    "apps.orders",
    "apps.trialkit",
    "apps.backoffice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.pricing.context_processors.gold_price",
                "apps.orders.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

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
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"apps": {"handlers": ["console"], "level": "INFO"}},
}

# --- Stripe ---
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")
# Demo mode: payments are simulated on a local checkout page, no Stripe account needed.
# On by default when no Stripe key is configured.
STRIPE_DEMO_MODE = env_bool("STRIPE_DEMO_MODE", not STRIPE_SECRET_KEY)
if STRIPE_DEMO_MODE and STRIPE_SECRET_KEY.startswith("sk_live_"):
    raise RuntimeError("STRIPE_DEMO_MODE cannot be enabled with a live Stripe key.")
CURRENCY = "eur"

# --- Gold spot price ---
GOLD_PRICE_PROVIDER = env("GOLD_PRICE_PROVIDER", "goldapicom")
GOLDAPI_KEY = env("GOLDAPI_KEY", "")
GOLD_PRICE_MAX_AGE_MINUTES = int(env("GOLD_PRICE_MAX_AGE_MINUTES", "1440"))
# VAT rate applied on top of the HT price (France: 20 %).
VAT_RATE = env("VAT_RATE", "0.20")

# --- Trial kit ---
TRIAL_KIT_MIN = int(env("TRIAL_KIT_MIN", "4"))
TRIAL_KIT_MAX = int(env("TRIAL_KIT_MAX", "4"))
# Amount paid for the kit (includes the refundable part below).
TRIAL_KIT_PRICE_CENTS = int(env("TRIAL_KIT_PRICE_CENTS", "10000"))
# Refunded once the kit is back and checked by the team.
TRIAL_KIT_REFUND_CENTS = int(env("TRIAL_KIT_REFUND_CENTS", "2000"))
# Deducted from the ring order with the kit's unique code (not refunded otherwise).
TRIAL_KIT_CREDIT_CENTS = int(env("TRIAL_KIT_CREDIT_CENTS", "8000"))
# Days after delivery to send the kit back, estimated transit time, reminder frequency.
TRIAL_KIT_RETURN_DAYS = int(env("TRIAL_KIT_RETURN_DAYS", "8"))
TRIAL_KIT_DELIVERY_DAYS = int(env("TRIAL_KIT_DELIVERY_DAYS", "2"))
TRIAL_KIT_REMINDER_EVERY_DAYS = int(env("TRIAL_KIT_REMINDER_EVERY_DAYS", "2"))

# --- Shop address (return label, packing slip) ---
SHOP_ADDRESS = env("SHOP_ADDRESS", "Maison Alliance — Atelier\\n1 rue de l'Exemple\\n69000 Lyon\\nFrance").replace("\\n", "\n")

# --- E-mails ---
# Default: e-mails are printed in the terminal (console). Set EMAIL_HOST… to send real e-mails.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend" if env("EMAIL_HOST") else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", f"{SITE_NAME} <bonjour@example.com>")
