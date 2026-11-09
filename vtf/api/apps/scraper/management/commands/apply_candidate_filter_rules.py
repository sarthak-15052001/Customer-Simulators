"""Management command: apply_candidate_filter_rules

Retroactively applies active CandidateFilterRule rows to existing
ScrapingCandidate rows (status not in imported/hidden). Matching
candidates are marked status="hidden" with an audit log entry, same
effect as the "Apply selected rule(s) to existing candidates" admin
action, but runnable from the CLI / a cron job.

Usage:
  python manage.py apply_candidate_filter_rules
  python manage.py apply_candidate_filter_rules --dry-run
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.scraper.models import CandidateFilterRule
from apps.scraper.services.filter_rules import apply_rules_retroactively


class Command(BaseCommand):
    help = "Apply active CandidateFilterRule rows to existing scraping candidates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be hidden without saving changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        rules = list(CandidateFilterRule.objects.filter(is_active=True).order_by("priority", "name"))
        if not rules:
            self.stdout.write(self.style.WARNING("No active filter rules found."))
            return

        affected, messages = apply_rules_retroactively(
            rules, actor="rule-engine", dry_run=dry_run
        )
        for message in messages:
            self.stdout.write(f"  {message}")

        verb = "Would hide" if dry_run else "Hidden"
        self.stdout.write(self.style.SUCCESS(f"{verb} {affected} candidate(s)."))
