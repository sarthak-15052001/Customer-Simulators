"""Scrape the VTF homepage top announcement banner via Playwright.

Usage:
  python manage.py scrape_header_banner
  python manage.py scrape_header_banner --lang FR
  python manage.py scrape_header_banner --async
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.header_scraper.services.scrape import LANGUAGE_URLS


class Command(BaseCommand):
    help = (
        "Scrape the live VTF Vacances top header banner with Playwright "
        "and auto-publish to HeaderBanner."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--lang",
            type=str,
            default="",
            help="FR or GB. Omit to scrape both.",
        )
        parser.add_argument(
            "--async",
            dest="use_async",
            action="store_true",
            help="Queue Celery instead of scraping in-process.",
        )

    def handle(self, *args, **options):
        language = (options.get("lang") or "").strip().upper()
        use_async = options["use_async"]

        if language and language not in LANGUAGE_URLS:
            raise CommandError(f"Unsupported --lang {language!r}. Use FR or GB.")

        if use_async:
            from apps.header_scraper.tasks import (
                task_scrape_header_banner,
                task_scrape_header_banner_language,
            )

            if language:
                result = task_scrape_header_banner_language.delay(language)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Queued language={language} task_id={result.id}"
                    )
                )
            else:
                result = task_scrape_header_banner.delay()
                self.stdout.write(
                    self.style.SUCCESS(f"Queued FR+GB task_id={result.id}")
                )
            return

        from apps.header_scraper.services.sync import sync_all_languages, sync_language

        if language:
            summary = sync_language(language)
            self.stdout.write(self.style.SUCCESS(str(summary)))
            return

        summary = sync_all_languages()
        self.stdout.write(self.style.SUCCESS(str(summary)))
