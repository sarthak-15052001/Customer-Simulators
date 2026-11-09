"""Auto hide/exclude rule engine for scraped candidates.

A CandidateFilterRule lets staff define, from Django admin, patterns such
as "name contains 'hotel' -> exclude" without any code change. This module
loads active rules and applies them to raw scraped items (before a
ScrapingCandidate row is created) and can also be re-applied to existing
candidates via the admin action / management command.

Usage in the pipeline:

    rules = get_active_rules()
    for cand in candidates:
        action, rule = match_rule(cand.nom, cand.region, cand.source, rules)
        if action == "exclude":
            continue  # never persisted
        elif action == "hide":
            ... create ScrapingCandidate with status="hidden" ...
"""
from __future__ import annotations

import logging
import re

from django.utils import timezone as dj_timezone

from apps.scraper.models import CandidateFilterRule, ScrapingCandidate, ScrapingImportLog

logger = logging.getLogger(__name__)

# Cache of compiled regexes keyed by (pattern, case_sensitive) so repeated
# calls within a single pipeline run don't recompile per-candidate.
_compiled_cache: dict[tuple[str, bool], re.Pattern] = {}


def get_active_rules(region: str | None = None, source: str | None = None):
    """Return active rules ordered by priority, optionally pre-filtered by
    a region / source they would even be eligible to apply to.

    A rule with a blank scope_region / scope_source applies globally; a
    rule with a scope set only applies when it matches that scope.
    """
    qs = CandidateFilterRule.objects.filter(is_active=True)
    rules = list(qs.order_by("priority", "name"))

    if region is None and source is None:
        return rules

    eligible = []
    for rule in rules:
        if rule.scope_region and region and rule.scope_region != region:
            continue
        if rule.scope_source and source and rule.scope_source != source:
            continue
        eligible.append(rule)
    return eligible


def _compile(pattern: str, case_sensitive: bool) -> re.Pattern | None:
    key = (pattern, case_sensitive)
    if key in _compiled_cache:
        return _compiled_cache[key]
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        logger.warning("filter_rules: invalid regex pattern=%r err=%s", pattern, exc)
        compiled = None
    _compiled_cache[key] = compiled
    return compiled


def _field_value(rule: CandidateFilterRule, nom: str, region: str, source: str, type_emoji: str = "") -> str:
    values = {
        "nom": nom or "",
        "region": region or "",
        "source": source or "",
        "type_emoji": type_emoji or "",
    }
    return values.get(rule.field, "")


def rule_matches(
    rule: CandidateFilterRule,
    *,
    nom: str,
    region: str = "",
    source: str = "",
    type_emoji: str = "",
) -> bool:
    """Return True if a single rule matches the given candidate values."""
    if rule.scope_region and region and rule.scope_region != region:
        return False
    if rule.scope_source and source and rule.scope_source != source:
        return False

    value = _field_value(rule, nom, region, source, type_emoji)
    if not value:
        return False

    if rule.is_regex:
        compiled = _compile(rule.pattern, rule.case_sensitive)
        if compiled is None:
            return False
        return compiled.search(value) is not None

    haystack = value if rule.case_sensitive else value.lower()
    needle = rule.pattern if rule.case_sensitive else rule.pattern.lower()
    return needle in haystack


def match_rule(
    nom: str,
    region: str = "",
    source: str = "",
    type_emoji: str = "",
    rules: list[CandidateFilterRule] | None = None,
) -> tuple[str | None, "CandidateFilterRule | None"]:
    """Evaluate rules (priority order) against a candidate.

    Returns (action, matched_rule) where action is "exclude", "hide", or
    None if nothing matched. Stops at the first match (priority order).
    """
    if rules is None:
        rules = get_active_rules(region=region, source=source)

    for rule in rules:
        if rule_matches(rule, nom=nom, region=region, source=source, type_emoji=type_emoji):
            return rule.action, rule
    return None, None


def apply_rules_retroactively(
    rules: list[CandidateFilterRule],
    *,
    actor: str,
    log_actor: str = "rule-engine",
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """Retroactively hide already-scraped candidates that match `rules`.

    Shared by the "Apply selected rule(s) to existing candidates" admin
    action and the `apply_candidate_filter_rules` management command, so
    the two consumers can't drift from each other.

    "Exclude" rules are applied here as a hide too (the row already
    exists, so it can't be un-created) with a note in `edits` for
    traceability.

    Args:
        rules: rules to evaluate, in the order they should be tried.
        actor: recorded on the candidate itself (`reviewed_by`) — e.g. the
            staff member's email from the admin, or "rule-engine" from the
            CLI/cron path.
        log_actor: recorded on the `ScrapingImportLog` entry. Defaults to
            "rule-engine" to match the automated-hide convention used by
            the pipeline; pass `actor` explicitly if the caller wants the
            log to show the human who triggered the retroactive run.
        dry_run: if True, nothing is saved; only the would-be-affected
            candidates and their names are returned.

    Returns:
        (affected_count, messages) where messages is a list of
        human-readable "<name> -> hidden (rule: <rule>)" strings, useful
        for CLI output.
    """
    candidates = ScrapingCandidate.objects.exclude(status__in=("imported", "hidden"))
    affected = 0
    messages: list[str] = []
    logs = []

    for candidate in candidates:
        for rule in rules:
            if rule_matches(
                rule,
                nom=candidate.nom,
                region=candidate.region,
                source=candidate.source,
                type_emoji=candidate.type_emoji,
            ):
                affected += 1
                messages.append(f"{candidate.nom!r} -> hidden (rule: {rule.name})")
                if not dry_run:
                    candidate.status = "hidden"
                    candidate.reviewed_by = actor
                    candidate.reviewed_at = dj_timezone.now()
                    candidate.edits = {
                        "reason": f"Auto-hidden retroactively by rule: {rule.name}"
                    }
                    candidate.save(
                        update_fields=["status", "reviewed_by", "reviewed_at", "edits"]
                    )
                    logs.append(
                        ScrapingImportLog(
                            job=candidate.job,
                            candidate=candidate,
                            action="auto_hide",
                            actor=log_actor,
                            reason=f"Matched filter rule (retroactive): {rule.name}",
                        )
                    )
                break

    if not dry_run and logs:
        ScrapingImportLog.objects.bulk_create(logs)

    return affected, messages
