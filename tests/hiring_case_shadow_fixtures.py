"""Synthetic variations of the existing Application Contract fixtures; never live data."""

from dataclasses import replace

from models.candidate_priority import CandidatePriority
from models.career_update import CareerUpdate
from models.hiring_case_shadow import ConfirmedCapabilityGap, HiringCaseShadowSource
from models.job_profile import JobProfile
from tests.test_application_contract import _candidate, _source


def fixture_source():
    return HiringCaseShadowSource(
        candidate=replace(_candidate(), target_role_families=["Product Ops"]),
        analysis_source=_source("potential"),
        job_profile=JobProfile(
            job_id="job-1", role_family="Product Operations",
            must_have_capabilities=["Root cause analysis"],
        ),
    )


def comparison_fixtures():
    direct = fixture_source()
    low_value = replace(
        direct,
        candidate=replace(direct.candidate, priorities=[CandidatePriority("Root cause analysis", "negative")]),
        job_profile=replace(direct.job_profile, key_responsibilities=["Root cause analysis"]),
        analysis_source=replace(direct.analysis_source, recommendation="best_match"),
    )
    gap = replace(
        direct,
        job_profile=replace(direct.job_profile, must_have_capabilities=["Cloud operations"]),
        career_updates=(CareerUpdate(
            id="gap-note", candidate_id=direct.candidate.id,
            update_type="reflection", description="I cannot operate production cloud systems yet.",
        ),),
        confirmed_gaps=(ConfirmedCapabilityGap(
            candidate_id=direct.candidate.id, job_id="job-1",
            requirement="Cloud operations", source_update_id="gap-note",
        ),),
    )
    missing = replace(
        direct, job_profile=replace(direct.job_profile, must_have_capabilities=["SQL"]),
    )
    transferable = replace(
        direct, job_profile=replace(direct.job_profile, must_have_capabilities=["Stakeholder communication"]),
        analysis_source=replace(direct.analysis_source, recommendation="competitive"),
    )
    blocked = replace(
        direct, analysis_source=replace(
            direct.analysis_source, recommendation="reject",
            analysis={"rule_rejection_type": "hard_filter", "hard_conflicts": ["Existing blocker"]},
        ),
    )
    legacy_good = replace(direct, analysis_source=replace(direct.analysis_source, recommendation="good_opportunity"))
    legacy_best = replace(direct, analysis_source=replace(direct.analysis_source, recommendation="best_match"))
    return [direct, low_value, gap, missing, transferable, blocked, legacy_good, legacy_best]
