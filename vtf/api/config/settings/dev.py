"""Local development settings."""
from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
SECRET_KEY = "django-insecure-dev-only-do-not-deploy"

# Ensure SQLite directory exists (compose mounts an empty volume on first run).
(BASE_DIR / ".data").mkdir(parents=True, exist_ok=True)
