from django.apps import AppConfig


class TariffScraperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tariff_scraper"
    verbose_name = "Tariff Scraper"

    def ready(self):
        # Injects the price-health summary into the admin index page context
        # so the client sees "global vision" counts the moment they log in,
        # without touching contrib.admin's own view code.
        from apps.tariff_scraper import admin_index  # noqa: F401