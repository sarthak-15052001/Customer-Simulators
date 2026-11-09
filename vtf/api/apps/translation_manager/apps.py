from __future__ import annotations

from django.apps import AppConfig


class TranslationManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.translation_manager"
    label = "translation_manager"
    verbose_name = "TRANSLATION MANAGER"

    def ready(self) -> None:
        from . import signals  # noqa: F401
