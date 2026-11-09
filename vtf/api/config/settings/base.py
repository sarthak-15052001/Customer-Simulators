"""Common settings shared by dev / prod.

Per `vtf/api/docs/CLAUDE.md`: env vars are read here only; services receive
their config as kwargs.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from celery.schedules import crontab as _crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from .env without overriding real environment vars."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / ".data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-change-me")
DEBUG = False
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 3rd-party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    # Local
    "apps.catalog",
    "apps.pricing",
    "apps.recommender",
    "apps.scraper",
    "apps.cache_orchestrator",
    "apps.mailer",
    "apps.tariff_scraper",
    "apps.header_scraper",
    "apps.translation_manager",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "common.middleware.ApiResponseTranslationMiddleware",
    "common.middleware.ApiRequestLoggingMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Default DB: file-backed SQLite under .data/ (matches docker-compose).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".data" / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# Django's stock fr locale renders dates long-form ("1 mars 2027") while any
# value we render ourselves from JSON arrives ISO ("2026-07-25"), so the admin
# showed two date formats side by side. Override the locale's formats with the
# numeric French form the VTF booking funnel itself uses ("01/08/2026"), which
# is compact enough for the dense tariff tables and unambiguous for staff.
# Anything rendering a raw JSON date string must call
# apps.tariff_scraper.admin_display.fr_date so both paths agree.
FORMAT_MODULE_PATH = ["config.formats"]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / ".data" / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    
    # ── Rate limiting (spec §5.2) ─────────────────────────────────────────
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "catalog_ip":           "1000/hour",
        "estimate_ip":          "200/hour",
        "recommend_ip":         "100/hour",
        "interactions_session": "100/hour",
    },
    # ── Custom exception handler ──────────────────────────────────────────
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "VTF Customer Simulators API",
    "DESCRIPTION": (
        "Backend powering the VTF customer simulator (catalog + pricing + "
        "recommendations). See vtf/api/docs/."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "FormuleEnum": "common.enums.Formule",
        # Two genuinely different "language" choice-sets exist across the
        # schema and were colliding under drf-spectacular's auto-generated
        # hashed names (Language9baEnum / Language16bEnum):
        #   1. Model-level fields with display labels — HeaderBanner.language,
        #      HeaderBannerSnapshot.language, TranslationEntry.language.
        "LanguageEnum": [("FR", "French"), ("GB", "English")],
        #   2. Manually-declared serializer ChoiceFields using plain string
        #      choices (no separate label) — TranslationTriggerRequestSerializer
        #      .language, HeaderScrapeRequestSerializer.language,
        #      HeaderDryRunAlertSerializer.language.
        "LanguageFilterEnum": [("FR", "FR"), ("GB", "GB")],
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "common.schema.add_global_language_parameter",
    ],
}

# ─── Logging ───────────────────────────────────────────────────────────────
# local.log      — Django/app activity (views, signals, registry sync).
# celery_logger.log — Celery worker, beat, task lifecycle (all apps with tasks).
# scraper_logger.log — tariff_scraper + header_scraper pipelines and Celery tasks.
# All file timestamps are Europe/Paris.
#
# translation_manager logging strategy:
#   • "translation_manager" — bare name used in tasks.py, signals.py, services/*
#     → local_file (app activity) + celery_file (task execution in Celery workers)
#   • "apps.translation_manager" — Django namespace used in views.py + any future
#     module-level getLogger(__name__) calls → same handler set as above.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "paris_verbose": {
            "()": "config.logging.ParisFormatter",
            "format": (
                "%(asctime)s %(levelname)s [%(process)d:%(threadName)s] "
                "%(name)s: %(message)s"
            ),
        },
        "paris_simple": {
            "()": "config.logging.ParisFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "paris_simple",
        },
        "local_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "local.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "paris_verbose",
        },
        "celery_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "celery_logger.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "paris_verbose",
        },
        "scraper_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "scraper_logger.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "paris_verbose",
        },
    },
    "root": {
        "handlers": ["console", "local_file"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console", "local_file"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.catalog": {
            "handlers": ["console", "local_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.mailer": {
            "handlers": ["console", "local_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.pricing": {
            "handlers": ["console", "local_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.recommender": {
            "handlers": ["console", "local_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        # translation_manager — two logger keys for full coverage:
        #
        #   "translation_manager" — bare name used in tasks.py, services/*.py,
        #     and signals.py (same non-namespaced pattern as "scraper" /
        #     "header_scraper" keys below).  Writes to both local_file (so API
        #     log viewer can surface it) AND celery_file (so Celery worker task
        #     runs are visible in the Celery log).
        #
        #   "apps.translation_manager" — proper Django app namespace; used in
        #     views.py where getLogger(__name__) would resolve to this.  Same
        #     handler set: local_file + celery_file so nothing is silently dropped
        #     regardless of which naming convention a module uses.
        "translation_manager": {
            "handlers": ["console", "local_file", "celery_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.translation_manager": {
            "handlers": ["console", "local_file", "celery_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.recommender.tasks": {
            "handlers": ["console", "local_file", "celery_file"],
            "level": os.environ.get("CELERY_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.scraper": {
            "handlers": ["console", "local_file", "scraper_file"],
            "level": os.environ.get("SCRAPER_LOG_LEVEL", os.environ.get("APP_LOG_LEVEL", "INFO")),
            "propagate": False,
        },
        "apps.scraper.tasks": {
            "handlers": ["console", "scraper_file"],
            "level": os.environ.get("SCRAPER_LOG_LEVEL", os.environ.get("CELERY_LOG_LEVEL", "INFO")),
            "propagate": False,
        },
        "apps.tariff_scraper": {
            "handlers": ["console", "local_file", "scraper_file"],
            "level": os.environ.get(
                "SCRAPER_LOG_LEVEL", os.environ.get("APP_LOG_LEVEL", "INFO")
            ),
            "propagate": False,
        },
        "scraper": {
            "handlers": ["console", "scraper_file"],
            "level": os.environ.get(
                "SCRAPER_LOG_LEVEL", os.environ.get("CELERY_LOG_LEVEL", "INFO")
            ),
            "propagate": False,
        },
        "tariff_scraper.alerts": {
            "handlers": ["console", "scraper_file"],
            "level": os.environ.get(
                "SCRAPER_LOG_LEVEL", os.environ.get("APP_LOG_LEVEL", "INFO")
            ),
            "propagate": False,
        },
        # header_scraper — Django app namespace (views, admin, serializers)
        # Goes to local_file + scraper_file so API hits appear in both logs.
        "apps.header_scraper": {
            "handlers": ["console", "local_file", "scraper_file"],
            "level": os.environ.get(
                "SCRAPER_LOG_LEVEL", os.environ.get("APP_LOG_LEVEL", "INFO")
            ),
            "propagate": False,
        },
        # Bare "header_scraper" name used in tasks.py, services/sync.py,
        # services/scrape.py — scraper pipeline output goes to scraper_file only
        # (same pattern as the "scraper" key used by tariff_scraper tasks).
        "header_scraper": {
            "handlers": ["console", "scraper_file"],
            "level": os.environ.get(
                "SCRAPER_LOG_LEVEL", os.environ.get("CELERY_LOG_LEVEL", "INFO")
            ),
            "propagate": False,
        },
        "common.api": {
            "handlers": ["console", "local_file"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "celery_file"],
            "level": os.environ.get("CELERY_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "celery.app.trace": {
            "handlers": ["console", "celery_file"],
            "level": os.environ.get("CELERY_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django_celery_beat": {
            "handlers": ["console", "celery_file"],
            "level": os.environ.get("CELERY_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# HMAC secret for /go/{token} booking-redirect signing. Falls back to
# SECRET_KEY when unset (dev only).
BOOKING_REDIRECT_SECRET = os.environ.get(
    "BOOKING_REDIRECT_SECRET", SECRET_KEY
)

# Base URL for generating absolute redirect URLs (e.g. bookingUrl in responses)
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
SECRET_IP_SALT = os.environ.get("SECRET_IP_SALT", "vtf-dev-ip-salt")

# Phase 2 — minimum SimulationLog rows before SVD collaborative filtering activates.
RECO_MIN_CF_INTERACTIONS = int(os.environ.get("RECO_MIN_CF_INTERACTIONS", "500"))

def _redis_url_with_db(redis_url: str, db: int) -> str:
    """Return *redis_url* with Redis logical DB set to *db*."""
    parsed = urlparse(redis_url)
    return urlunparse(parsed._replace(path=f"/{db}"))


def _default_celery_redis_urls(redis_url: str) -> tuple[str, str]:
    """Derive Celery broker/result URLs from the cache ``REDIS_URL``.

    Uses adjacent DB indexes so cache, broker, and results do not collide:
    cache DB *N* → broker *N+1*, results *N+2*.
    """
    parsed = urlparse(redis_url)
    path = (parsed.path or "/0").strip("/")
    try:
        cache_db = int(path) if path else 0
    except ValueError:
        cache_db = 0
    return (
        _redis_url_with_db(redis_url, cache_db + 1),
        _redis_url_with_db(redis_url, cache_db + 2),
    )

_redis_url = os.environ.get("REDIS_URL")
CACHES = {
    "default": (
        {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
        if _redis_url
        else {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "vtf-locmem",
        }
    ),
}

# Phase 3 — optional webhook when cache rebuild completes (spec §5.1).
CACHE_REBUILD_NOTIFY = os.environ.get("CACHE_REBUILD_NOTIFY", "false").lower() in (
    "1",
    "true",
    "yes",
)
# Shared Discord webhook — used by cache_orchestrator (rebuild notifications)
# and apps.scraper.tasks (new-candidate alerts). Same URL for both, single env var.
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
NOTIFICATION_ENVIRONMENT_NAME = os.environ.get("NOTIFICATION_ENVIRONMENT_NAME", "")
NOTIFICATION_ORIGIN_DOMAIN = os.environ.get("NOTIFICATION_ORIGIN_DOMAIN", "")
NOTIFICATION_ORIGIN_IP = os.environ.get("NOTIFICATION_ORIGIN_IP", "")

# Tariff scraper: send 🟢 green Discord alert when a village scrapes successfully.
# Default ON so the client always sees success / warning / failure colours.
TARIFF_SCRAPER_NOTIFY_SUCCESS = os.environ.get(
    "TARIFF_SCRAPER_NOTIFY_SUCCESS", "true"
).lower() in ("1", "true", "yes")

# Header scraper: send 🟢 green Discord alert when a homepage banner changes
# and is published. Default ON, same behaviour as the tariff scraper above.
HEADER_SCRAPER_NOTIFY_SUCCESS = os.environ.get(
    "HEADER_SCRAPER_NOTIFY_SUCCESS", "true"
).lower() in ("1", "true", "yes")


# ─── Brevo transactional email ────────────────────────────────────────────
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "noreply@vtf-vacances.com")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "VTF Vacances")

# ─── Runtime translation LLM ──────────────────────────────────────────────
LLM_FALLBACK_ENABLED = os.environ.get("LLM_FALLBACK_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
LMSTUDIO_BASE_URL = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "luth-lfm2-350m")
LLM_MAX_RETRIES = os.environ.get("LLM_MAX_RETRIES", "2")
TRANSLATION_LLM_MAX_TOKENS = os.environ.get("TRANSLATION_LLM_MAX_TOKENS", "12000")
TRANSLATION_LLM_ENABLED = os.environ.get("TRANSLATION_LLM_ENABLED", "false")
TRANSLATION_GLOBAL_RESPONSES_ENABLED = os.environ.get(
    "TRANSLATION_GLOBAL_RESPONSES_ENABLED",
    "true",
)
TRANSLATION_LLM_TIMEOUT_SECONDS = os.environ.get(
    "TRANSLATION_LLM_TIMEOUT_SECONDS",
    "900",
)
# Sections/batches larger than this (in JSON chars, ~4 chars/token) are split
# further before being sent to the LLM — see translations.py for why.
TRANSLATION_LLM_CHUNK_CHAR_BUDGET = os.environ.get(
    "TRANSLATION_LLM_CHUNK_CHAR_BUDGET",
    "2000",
)
TRANSLATION_CACHE_TTL = os.environ.get("TRANSLATION_CACHE_TTL", str(60 * 60 * 24 * 7))


# ─── Celery configuration ─────────────────────────────────────────────────────

_data_dir = Path(__file__).resolve().parent.parent.parent / ".data"

# Celery broker/result backend:
#   • Explicit CELERY_BROKER_URL / CELERY_RESULT_BACKEND always win.
#   • When REDIS_URL is set (cache on Redis), default Celery to Redis too.
#   • Otherwise fall back to SQLite for zero-dependency local dev.
if _redis_url:
    _celery_broker_default, _celery_result_default = _default_celery_redis_urls(
        _redis_url
    )
else:
    _celery_broker_default = f"sqla+sqlite:///{_data_dir / 'celery.sqlite3'}"
    _celery_result_default = f"db+sqlite:///{_data_dir / 'celery-results.sqlite3'}"

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", _celery_broker_default)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", _celery_result_default
)

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE  # noqa: F821
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_ACKS_LATE = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# ─── Cron schedule (AC2.7 / AC2.14) ──────────────────────────────────────────
CELERY_BEAT_SCHEDULE = {
    # AC2.7 — Popularity cache refresh every 6 hours
    "refresh-popularity": {
        "task": "apps.recommender.tasks.task_refresh_popularity",
        "schedule": _crontab(minute=0, hour="*/6"),
    },
    # AC2.14 — Check CF thresholds daily at 02:50 (before train at 03:00)
    "check-cf-readiness": {
        "task": "apps.recommender.tasks.task_check_cf_readiness",
        "schedule": _crontab(minute=50, hour=2),
    },
    # AC2.14 — Train SVD model daily at 03:00 AM
    "train-cf-model": {
        "task": "apps.recommender.tasks.task_train_cf_model",
        "schedule": _crontab(minute=0, hour=3),
    },
    # Rebuild cache every morning at 07:00 (Phase 3)
    "rebuild-cache-daily-7am": {
        "task": "apps.cache_orchestrator.tasks.task_rebuild_cache",
        "schedule": _crontab(minute=0, hour=7),
        "kwargs": {
            "scope": "all",
            "reason": "Scheduled daily 07:00 cache rebuild",
            "triggered_by": "system:cron",
        },
    },
    # Monthly activity scrape (1st of each month at 04:00)
    "monthly-scrape-all": {
        "task": "apps.scraper.tasks.task_monthly_scrape_all",
        "schedule": _crontab(minute=0, hour=4, day_of_month=1),
    },
    # VTF homepage top banner — every 4 hours exactly on the hour
    "scrape-header-banner": {
        "task": "apps.header_scraper.tasks.task_scrape_header_banner",
        "schedule": _crontab(minute=0, hour="*/4"),
    },
}
