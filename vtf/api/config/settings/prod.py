from __future__ import annotations

import os

from .base import *  # noqa: F401,F403


if not os.environ.get("DJANGO_SECRET_KEY"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]
CORS_ALLOWED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]
# --- Static files via WhiteNoise ---
# Insert WhiteNoise right after SecurityMiddleware, preserving base.py's middleware.

STATIC_URL = "/static/"
STATIC_ROOT = "/var/www/html/.data/staticfiles"
DEBUG = True
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# --- Static files via WhiteNoise ---
# Insert WhiteNoise right after SecurityMiddleware, preserving base.py's middleware.
MIDDLEWARE = list(MIDDLEWARE)  # copy the list inherited from base
if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
    _sec = "django.middleware.security.SecurityMiddleware"
    if _sec in MIDDLEWARE:
        MIDDLEWARE.insert(MIDDLEWARE.index(_sec) + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
    else:
        MIDDLEWARE.insert(0, "whitenoise.middleware.WhiteNoiseMiddleware")

STATIC_URL = "/static/"
STATIC_ROOT = "/var/www/html/.data/staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}