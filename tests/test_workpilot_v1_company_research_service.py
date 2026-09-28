from types import SimpleNamespace

import pytest

from services.company_research_service import (
    CompanyResearchService,
    PublicResearchPage,
    _materialize_company_profile,
    _source_type,
)


def page(
    ref,
    text,
    *,
    source_type="company_website",
):
    return PublicResearchPage(
        ref=ref,
        title="Public source",
        source_type=source_type,
        text=text,
    )


def test_company_profile_material_requires_exact_source_excerpt():
    ref = "https://example.com/company"

    sources, draft = _materialize_company_profile(
        company_id="company-1",
        pages=[
            page(
                ref,
                (
                    "Example builds managed infrastructure services. "
                    "The company expanded its cloud operations in 2026."
                ),
            )
        ],
        payload={
            "what_they_do": {
                "value": (
                    "Example builds managed infrastructure services."
                ),
                "source_ref": ref,
            },
            "products_services": [],
            "market_context": [],
            "size_context": None,
            "public_culture_signals": [],
            "public_strategy_priorities": [],
            "recent_developments": [
                {
                    "value": (
                        "The company expanded its cloud operations in 2026."
                    ),
                    "source_ref": ref,
                }
            ],
            "uncertainties": [
                "Client allocation is not public.",
            ],
        },
    )

    assert (
        draft.what_they_do
        == "Example builds managed infrastructure services."
    )

    assert draft.recent_developments == (
        "The company expanded its cloud operations in 2026.",
    )

    assert len(sources) == 1

    assert (
        draft.claims[0].value
        in sources[0].summary
    )


def test_paraphrased_or_unknown_source_claim_is_rejected():
    ref = "https://example.com/company"

    with pytest.raises(
        ValueError,
        match="No grounded",
    ):
        _materialize_company_profile(
            company_id="company-1",
            pages=[
                page(
                    ref,
                    "Example provides managed services.",
                )
            ],
            payload={
                "what_they_do": {
                    "value": (
                        "Example is a global AI infrastructure leader."
                    ),
                    "source_ref": ref,
                },
                "products_services": [],
                "market_context": [],
                "size_context": None,
                "public_culture_signals": [],
                "public_strategy_priorities": [],
                "recent_developments": [],
                "uncertainties": [],
            },
        )


def test_source_type_classification_keeps_job_and_company_distinct():
    assert _source_type(
        (
            "https://astreya.wd5.myworkdayjobs.com/"
            "en-US/jobs/job/Dublin/Role"
        ),
        "Astreya",
    ) == "public_job_posting"

    assert _source_type(
        "https://astreya.com/solutions/example",
        "Astreya",
    ) == "company_website"

    assert _source_type(
        "https://news.cognizant.com/acquisition",
        "Astreya",
    ) == "professional_news"


class Registry:
    def __init__(self):
        self.calls = []

    def get_or_create_company(
        self,
        name,
    ):
        self.calls.append(name)

        return SimpleNamespace(
            id="company-1",
            canonical_name=name,
        )


class Profiles:
    def __init__(self, current=None):
        self.value = current
        self.saved = []

    def current(
        self,
        _company_id,
    ):
        return self.value

    def save(
        self,
        profile,
    ):
        self.saved.append(profile)
        self.value = profile


class Discovery:
    def __init__(self):
        self.calls = []

    def discover(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)

        return [
            "https://example.com/company"
        ]


class Fetcher:
    def __init__(self):
        self.calls = []

    def fetch(
        self,
        url,
        *,
        company_name,
    ):
        self.calls.append(
            (url, company_name)
        )

        return page(
            url,
            (
                "Example provides managed infrastructure services. "
                "Example expanded its cloud operations in 2026."
            ),
        )


class Interpreter:
    def __init__(self):
        self.calls = []

    def interpret(
        self,
        *,
        company_id,
        company_name,
        pages,
    ):
        self.calls.append(
            (
                company_id,
                company_name,
                pages,
            )
        )

        return _materialize_company_profile(
            company_id=company_id,
            pages=pages,
            payload={
                "what_they_do": {
                    "value": (
                        "Example provides managed infrastructure services."
                    ),
                    "source_ref": pages[0].ref,
                },
                "products_services": [],
                "market_context": [],
                "size_context": None,
                "public_culture_signals": [],
                "public_strategy_priorities": [],
                "recent_developments": [
                    {
                        "value": (
                            "Example expanded its cloud operations in 2026."
                        ),
                        "source_ref": pages[0].ref,
                    }
                ],
                "uncertainties": [],
            },
        )


def test_service_reuses_existing_profile_without_network_work():
    existing = SimpleNamespace(
        company_id="company-1"
    )

    discovery = Discovery()

    service = CompanyResearchService(
        company_repository=Registry(),
        profile_repository=Profiles(
            existing
        ),
        discovery=discovery,
        fetcher=Fetcher(),
        interpreter=Interpreter(),
    )

    result = service.build_if_missing(
        company_name="Example",
    )

    assert result is existing
    assert discovery.calls == []


def test_service_builds_and_saves_grounded_profile_once():
    registry = Registry()
    profiles = Profiles()
    discovery = Discovery()
    fetcher = Fetcher()
    interpreter = Interpreter()

    service = CompanyResearchService(
        company_repository=registry,
        profile_repository=profiles,
        discovery=discovery,
        fetcher=fetcher,
        interpreter=interpreter,
    )

    profile = service.build_if_missing(
        company_name="Example",
        job_title="Incident Analyst",
        job_location="Dublin",
    )

    assert profile.company_id == "company-1"
    assert profile.profile_version == 1
    assert len(profiles.saved) == 1

    # Cached snapshot means no second research call.
    same = service.build_if_missing(
        company_name="Example",
        job_title="Incident Analyst",
        job_location="Dublin",
    )

    assert same is profile
    assert len(discovery.calls) == 1
    assert len(fetcher.calls) == 1
    assert len(interpreter.calls) == 1

def test_explicit_refresh_can_create_next_immutable_profile_version():
    registry = Registry()
    profiles = Profiles()
    discovery = Discovery()
    fetcher = Fetcher()
    interpreter = Interpreter()

    service = CompanyResearchService(
        company_repository=registry,
        profile_repository=profiles,
        discovery=discovery,
        fetcher=fetcher,
        interpreter=interpreter,
    )

    first = service.build_if_missing(
        company_name="Example",
        job_title="Incident Analyst",
        job_location="Dublin",
    )

    assert first.profile_version == 1

    class ChangedFetcher:
        def fetch(
            self,
            url,
            *,
            company_name,
        ):
            return page(
                url,
                (
                    "Example provides advanced managed infrastructure services. "
                    "Example expanded global cloud operations in 2026."
                ),
            )

    class ChangedInterpreter:
        def interpret(
            self,
            *,
            company_id,
            company_name,
            pages,
        ):
            return _materialize_company_profile(
                company_id=company_id,
                pages=pages,
                payload={
                    "what_they_do": {
                        "value": (
                            "Example provides advanced managed infrastructure services."
                        ),
                        "source_ref": pages[0].ref,
                    },
                    "products_services": [],
                    "market_context": [],
                    "size_context": None,
                    "public_culture_signals": [],
                    "public_strategy_priorities": [],
                    "recent_developments": [
                        {
                            "value": (
                                "Example expanded global cloud operations in 2026."
                            ),
                            "source_ref": pages[0].ref,
                        }
                    ],
                    "uncertainties": [],
                },
            )

    service.fetcher = ChangedFetcher()
    service.interpreter = ChangedInterpreter()

    second = service.refresh(
        company_name="Example",
        job_title="Incident Analyst",
        job_location="Dublin",
    )

    assert second.profile_version == 2
    assert second.supersedes_version == 1
    assert second.source_signature != first.source_signature
    assert profiles.current("company-1") is second

    calls_before = len(discovery.calls)

    cached = service.build_if_missing(
        company_name="Example",
    )

    assert cached is second
    assert len(discovery.calls) == calls_before


def test_company_research_provider_failure_is_normalized():
    import requests

    from services.company_research_service import (
        OpenAICompanyResearchDiscovery,
    )
    from services.provider_failure import ProviderFailure

    class Responses:
        def create(self, **_kwargs):
            raise requests.Timeout(
                "provider detail must not escape"
            )

    class Client:
        responses = Responses()

    discovery = OpenAICompanyResearchDiscovery(
        client=Client(),
        model="test-model",
    )

    with pytest.raises(
        ProviderFailure,
        match="provider_timeout",
    ):
        discovery.discover(
            company_name="Example",
        )
