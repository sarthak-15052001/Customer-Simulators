"""Unit tests for apps.scraper.services.filter_rules.

Covers the matching engine itself (rule_matches / match_rule / priority
ordering / scope semantics / invalid-pattern handling) plus the shared
apply_rules_retroactively() helper used by both the admin action and the
apply_candidate_filter_rules management command. None of this was
covered by tests before (see PR review, finding D).
"""
from __future__ import annotations

import pytest

from apps.scraper.models import CandidateFilterRule, ScrapingCandidate, ScrapingJob
from apps.scraper.services.filter_rules import (
    apply_rules_retroactively,
    match_rule,
    rule_matches,
)


def _rule(**kwargs) -> CandidateFilterRule:
    """Build an unsaved CandidateFilterRule with sane defaults."""
    defaults = dict(
        name="test-rule",
        field="nom",
        pattern="hotel",
        is_regex=False,
        case_sensitive=False,
        action="exclude",
        is_active=True,
        scope_region="",
        scope_source="",
        priority=0,
    )
    defaults.update(kwargs)
    return CandidateFilterRule(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# rule_matches: plain text vs regex, case sensitivity
# ─────────────────────────────────────────────────────────────────────────────

def test_plain_text_match_is_case_insensitive_by_default():
    rule = _rule(pattern="hotel", is_regex=False, case_sensitive=False)
    assert rule_matches(rule, nom="Grand HOTEL Biarritz") is True


def test_plain_text_case_sensitive_rejects_different_case():
    rule = _rule(pattern="Hotel", is_regex=False, case_sensitive=True)
    assert rule_matches(rule, nom="Grand hotel Biarritz") is False


def test_plain_text_case_sensitive_accepts_matching_case():
    rule = _rule(pattern="Hotel", is_regex=False, case_sensitive=True)
    assert rule_matches(rule, nom="Grand Hotel Biarritz") is True


def test_regex_match():
    rule = _rule(pattern=r"^Hotel\s", is_regex=True, case_sensitive=False)
    assert rule_matches(rule, nom="Hotel des Dunes") is True
    assert rule_matches(rule, nom="Le Hotel des Dunes") is False


def test_no_match_returns_false():
    rule = _rule(pattern="hotel", is_regex=False)
    assert rule_matches(rule, nom="Surf School Biarritz") is False


def test_blank_field_value_never_matches():
    rule = _rule(pattern="hotel", is_regex=False)
    assert rule_matches(rule, nom="") is False


# ─────────────────────────────────────────────────────────────────────────────
# rule_matches: invalid regex handling (finding A - validation)
# ─────────────────────────────────────────────────────────────────────────────

def test_invalid_regex_does_not_match_and_does_not_raise():
    rule = _rule(pattern="hotel(", is_regex=True)
    assert rule_matches(rule, nom="hotel(") is False


# ─────────────────────────────────────────────────────────────────────────────
# rule_matches: scope semantics (finding: scope on blank region/source)
# ─────────────────────────────────────────────────────────────────────────────

def test_region_scoped_rule_matches_same_region():
    rule = _rule(pattern="hotel", scope_region="Aquitaine / Landes")
    assert rule_matches(rule, nom="Hotel X", region="Aquitaine / Landes") is True


def test_region_scoped_rule_does_not_match_different_region():
    rule = _rule(pattern="hotel", scope_region="Aquitaine / Landes")
    assert rule_matches(rule, nom="Hotel X", region="Savoie") is False


def test_region_scoped_rule_applies_when_candidate_region_is_blank():
    """Documents current behavior: a blank candidate region is treated as
    "unknown", so the scope check is skipped and the rule still applies.
    This is the semantics called out in the PR review as worth a
    deliberate decision; captured here so a future change is a visible
    test update rather than a silent behavior change.
    """
    rule = _rule(pattern="hotel", scope_region="Aquitaine / Landes")
    assert rule_matches(rule, nom="Hotel X", region="") is True


def test_source_scoped_rule_respects_source():
    rule = _rule(pattern="hotel", scope_source="google_places")
    assert rule_matches(rule, nom="Hotel X", source="google_places") is True
    assert rule_matches(rule, nom="Hotel X", source="ot_local") is False


# ─────────────────────────────────────────────────────────────────────────────
# match_rule: priority / first-match ordering
# ─────────────────────────────────────────────────────────────────────────────

def test_match_rule_returns_none_when_nothing_matches():
    rules = [_rule(pattern="hotel")]
    action, matched = match_rule(nom="Surf School", rules=rules)
    assert action is None
    assert matched is None


def test_match_rule_stops_at_first_matching_rule_in_priority_order():
    exclude_rule = _rule(name="exclude-hotels", pattern="hotel", action="exclude", priority=0)
    hide_rule = _rule(name="hide-hotels", pattern="hotel", action="hide", priority=10)
    action, matched = match_rule(nom="Grand Hotel", rules=[exclude_rule, hide_rule])
    assert action == "exclude"
    assert matched is exclude_rule


def test_match_rule_respects_caller_supplied_priority_ordering():
    # Caller is responsible for ordering `rules`; match_rule takes the
    # first match in the list it's given, so a lower-priority rule placed
    # first in the list wins even though its .priority value is higher.
    later_priority_first = _rule(name="hide-hotels", pattern="hotel", action="hide", priority=10)
    earlier_priority_second = _rule(name="exclude-hotels", pattern="hotel", action="exclude", priority=0)
    action, matched = match_rule(
        nom="Grand Hotel", rules=[later_priority_first, earlier_priority_second]
    )
    assert action == "hide"
    assert matched is later_priority_first


# ─────────────────────────────────────────────────────────────────────────────
# apply_rules_retroactively
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def scraping_job_for_rules(db):
    from django.utils import timezone as dj_timezone

    return ScrapingJob.objects.create(
        id="scrape-filter-rules-test",
        target_type="village",
        target_id="biarritz",
        sources=["google_places"],
        radius_km=30,
        status="completed",
        triggered_by="test",
        started_at=dj_timezone.now(),
        completed_at=dj_timezone.now(),
    )


@pytest.fixture
def new_candidate_for_rules(db, scraping_job_for_rules):
    return ScrapingCandidate.objects.create(
        id="cand-filter-rules-test",
        job=scraping_job_for_rules,
        region="Aquitaine / Landes",
        source="google_places",
        source_url="https://example.com/hotel",
        source_id="hotel-retro-001",
        nom="Grand Hotel Biarritz",
        type_emoji="hotel",
        distance_km=1.0,
        status="new",
    )


@pytest.mark.django_db
def test_apply_rules_retroactively_hides_matching_candidate(new_candidate_for_rules):
    rule = CandidateFilterRule.objects.create(
        name="Hide hotels retro",
        field="nom",
        pattern="hotel",
        is_regex=False,
        action="hide",
        is_active=True,
    )

    affected, messages = apply_rules_retroactively([rule], actor="staff@example.com")

    new_candidate_for_rules.refresh_from_db()
    assert affected == 1
    assert len(messages) == 1
    assert new_candidate_for_rules.status == "hidden"
    assert new_candidate_for_rules.reviewed_by == "staff@example.com"


@pytest.mark.django_db
def test_apply_rules_retroactively_dry_run_does_not_save(new_candidate_for_rules):
    rule = CandidateFilterRule.objects.create(
        name="Hide hotels retro",
        field="nom",
        pattern="hotel",
        is_regex=False,
        action="hide",
        is_active=True,
    )

    affected, messages = apply_rules_retroactively(
        [rule], actor="staff@example.com", dry_run=True
    )

    new_candidate_for_rules.refresh_from_db()
    assert affected == 1
    assert len(messages) == 1
    assert new_candidate_for_rules.status == "new"  # unchanged


@pytest.mark.django_db
def test_apply_rules_retroactively_no_match_leaves_candidate_untouched(
    new_candidate_for_rules,
):
    rule = CandidateFilterRule.objects.create(
        name="Hide restaurants",
        field="nom",
        pattern="restaurant",
        is_regex=False,
        action="hide",
        is_active=True,
    )

    affected, messages = apply_rules_retroactively([rule], actor="staff@example.com")

    new_candidate_for_rules.refresh_from_db()
    assert affected == 0
    assert messages == []
    assert new_candidate_for_rules.status == "new"


# ─────────────────────────────────────────────────────────────────────────────
# CandidateFilterRule.clean(): invalid regex rejected at save time
# ─────────────────────────────────────────────────────────────────────────────

def test_clean_rejects_invalid_regex_pattern():
    from django.core.exceptions import ValidationError

    rule = _rule(pattern="hotel(", is_regex=True)
    with pytest.raises(ValidationError):
        rule.clean()


def test_clean_accepts_valid_regex_pattern():
    rule = _rule(pattern="^hotel", is_regex=True)
    rule.clean()  # should not raise


def test_clean_skips_regex_validation_for_plain_text_rules():
    rule = _rule(pattern="hotel(", is_regex=False)
    rule.clean()  # should not raise: not treated as regex
