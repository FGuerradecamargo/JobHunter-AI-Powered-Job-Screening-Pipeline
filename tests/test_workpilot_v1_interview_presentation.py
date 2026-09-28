from dataclasses import fields
import inspect
from types import SimpleNamespace

from services.interview_preparation_ui import (
    InterviewPreparationView,
    PreparationAreaView,
    _render_company_brief,
    load_company_profile_for_interview,
    render_interview_preparation_overview,
)


def test_presentation_view_keeps_source_and_gap_identity():
    area_names = {
        item.name
        for item in fields(
            PreparationAreaView
        )
    }

    view_names = {
        item.name
        for item in fields(
            InterviewPreparationView
        )
    }

    assert {
        "source_type",
        "gap_type",
    } <= area_names

    assert (
        "evidence_examples"
        in view_names
    )


def test_company_brief_lookup_is_read_only():
    company = SimpleNamespace(
        id="company-1",
    )

    profile = SimpleNamespace(
        company_id="company-1",
    )

    class Companies:
        def __init__(self):
            self.calls = []

        def find_company(
            self,
            name,
        ):
            self.calls.append(name)
            return company

    class Profiles:
        def __init__(self):
            self.calls = []

        def current(
            self,
            company_id,
        ):
            self.calls.append(
                company_id
            )
            return profile

    companies = Companies()
    profiles = Profiles()

    found_company, found_profile = (
        load_company_profile_for_interview(
            "Example",
            company_repository=companies,
            profile_repository=profiles,
        )
    )

    assert found_company is company
    assert found_profile is profile
    assert companies.calls == [
        "Example"
    ]
    assert profiles.calls == [
        "company-1"
    ]


def test_compact_overview_replaces_repetitive_area_dump():
    source = inspect.getsource(
        render_interview_preparation_overview
    )

    assert "Core topics" in source
    assert (
        "Evidence you can draw from"
        in source
    )
    assert (
        "Areas to handle carefully"
        in source
    )
    assert 'section_expander("Practice", expanded=False)' in source
    assert "Questions to ask" in source

    assert "Example direction:" not in source
    assert "Emphasis:" not in source
    assert "Keep in mind:" not in source


def test_company_brief_is_rendered_before_candidate_preparation():
    source = inspect.getsource(
        render_interview_preparation_overview
    )

    assert (
        source.index(
            "_render_company_brief("
        )
        < source.index(
            "#### Prepare for your interview"
        )
    )


def test_company_research_is_explicit_not_automatic():
    source = inspect.getsource(
        _render_company_brief
    )

    assert (
        source.index(
            'if button('
        )
        < source.index(
            ".build_if_missing("
        )
    )

    assert ".refresh(" not in source
