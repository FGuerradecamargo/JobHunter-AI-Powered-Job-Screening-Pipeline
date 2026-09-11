from __future__ import annotations

from dataclasses import asdict
import re

from models.application_context import ApplicationContext, PositioningTheme
from models.application_contract import ApplicationAnalysisSource, ApplicationContract
from services.career_memory_source_builder import build_source_signature
from services.role_family_normalizer import normalize_role_family


APPLICATION_CONTEXT_SCHEMA_VERSION = "application-context-v1"

_DIRECT_AUTHORITIES = {"professional_fact", "candidate_update"}
_TRANSFERABLE_AUTHORITIES = {"transferable_evidence"}
_SUPPORTING_AUTHORITIES = {"candidate_profile_fact"}
_DEVELOPING_AUTHORITIES = {"developing_evidence"}


def _normalize(value) -> str:
    value = re.sub(r"\s+", " ", str(value or "").strip())
    return re.sub(r"[.;:,]+$", "", value).strip()


def _strings(values) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    result = {_normalize(value) for value in values or [] if _normalize(value)}
    return sorted(result, key=str.casefold)


def _order_insensitive(value):
    if isinstance(value, dict):
        return {
            str(key): _order_insensitive(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set)):
        items = [_order_insensitive(item) for item in value]
        return sorted(items, key=lambda item: build_source_signature({"item": item}))
    if isinstance(value, str):
        return _normalize(value)
    return value


def _analysis_selectors(analysis: dict) -> dict[str, str]:
    market_signal = analysis.get("market_signal", {})
    if not isinstance(market_signal, dict):
        market_signal = {}
    labels = [
        *(
            analysis.get("requirements_met", [])
            if isinstance(analysis.get("requirements_met", []), list)
            else []
        ),
        *(
            analysis.get("strengths", [])
            if isinstance(analysis.get("strengths", []), list)
            else []
        ),
        *(
            market_signal.get("market_strengths", [])
            if isinstance(market_signal.get("market_strengths", []), list)
            else []
        ),
    ]
    return {
        normalized.casefold(): normalized
        for normalized in _strings(labels)
    }


def build_application_context(
    *,
    contract: ApplicationContract,
    analysis_source: ApplicationAnalysisSource,
) -> ApplicationContext:
    if not contract.eligible:
        raise ValueError("Application contract is not eligible.")
    if contract.candidate_id != analysis_source.candidate_id:
        raise PermissionError("Application contract belongs to another candidate.")
    if contract.job_id != analysis_source.job_id:
        raise PermissionError("Application contract belongs to another job.")
    if contract.analysis_id != analysis_source.analysis_id:
        raise PermissionError("Application contract belongs to another analysis.")

    selectors = _analysis_selectors(analysis_source.analysis)
    selected = [
        item
        for item in contract.evidence_refs
        if _normalize(item.statement).casefold() in selectors
    ]
    selected.sort(key=lambda item: item.evidence_ref)

    direct = [item for item in selected if item.authority in _DIRECT_AUTHORITIES]
    transferable = [
        item for item in selected if item.authority in _TRANSFERABLE_AUTHORITIES
    ]
    supporting = [
        item for item in selected if item.authority in _SUPPORTING_AUTHORITIES
    ]
    developing = [
        item for item in selected if item.authority in _DEVELOPING_AUTHORITIES
    ]

    refs_by_statement = {}
    for item in selected:
        key = _normalize(item.statement).casefold()
        refs_by_statement.setdefault(key, set()).add(item.evidence_ref)
    themes = [
        PositioningTheme(
            theme=label,
            evidence_refs=sorted(refs_by_statement[key]),
        )
        for key, label in selectors.items()
        if key in refs_by_statement
    ]
    themes.sort(key=lambda item: item.theme.casefold())

    market_signal = analysis_source.analysis.get("market_signal", {})
    if not isinstance(market_signal, dict):
        market_signal = {}

    signature_payload = {
        "contract_signature": contract.source_signature,
        "job": _order_insensitive(analysis_source.job),
        "analysis_id": analysis_source.analysis_id,
        "analysis_fields": _order_insensitive(
            {
                "job_level": analysis_source.analysis.get("job_level", ""),
                "core_requirements": analysis_source.analysis.get(
                    "core_requirements", []
                ),
                "requirements_met": analysis_source.analysis.get(
                    "requirements_met", []
                ),
                "strengths": analysis_source.analysis.get("strengths", []),
                "market_signal": market_signal,
                "development_gaps": contract.development_gaps,
                "structural_gaps": contract.structural_gaps,
            }
        ),
    }

    return ApplicationContext(
        candidate_id=contract.candidate_id,
        job_id=contract.job_id,
        analysis_id=contract.analysis_id,
        contract_signature=contract.source_signature,
        job_title=_normalize(analysis_source.job.get("title")),
        company=_normalize(analysis_source.job.get("company")),
        role_family=normalize_role_family(market_signal.get("role_family")),
        job_level=_normalize(analysis_source.analysis.get("job_level")),
        core_requirements=_strings(
            analysis_source.analysis.get("core_requirements", [])
        ),
        direct_evidence=direct,
        transferable_evidence=transferable,
        supporting_evidence=supporting,
        developing_evidence=developing,
        available_evidence=sorted(
            contract.evidence_refs,
            key=lambda item: item.evidence_ref,
        ),
        development_gaps=list(contract.development_gaps),
        structural_gaps=list(contract.structural_gaps),
        positioning_themes=themes,
        source_signature=build_source_signature(signature_payload),
        schema_version=APPLICATION_CONTEXT_SCHEMA_VERSION,
        recommendation=contract.recommendation,
        eligible=contract.eligible,
    )
