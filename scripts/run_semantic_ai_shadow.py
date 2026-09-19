"""Dry-run by default. Only a frozen, small synthetic batch can be authorized."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.semantic_evidence import SemanticSupportRelation, SemanticCoverage
from models.profile_interpretation import HardJobFact
from models.structured_interpretation import RegisteredSourceRef, SourceRefClass
from services.ai.openai_semantic_interpreter import (
    OpenAISemanticEvidenceInterpreter, read_semantic_shadow_config,
    compare_semantic_shadow, shadow_diagnostics,
)
from tests.semantic_evidence_v1_runner import references, project
from tests.hiring_case_adversarial_cases import adversarial_cases
from tests.hiring_case_adversarial_runner import digest
from scripts.semantic_shadow_batches import BATCH_002_IDS, selected_batch_002_case
from services.ai.semantic_shadow_request import PROMPT_VERSION

CASE_IDS = ("SE01", "SE03", "SE05", "SE10", "AV06", "SE13", "SE31", "SE02")


def selected_case(case_id):
    if case_id not in CASE_IDS:
        raise ValueError("case_not_in_frozen_batch")
    if case_id != "AV06":
        original = Path(__file__).resolve().parents[1] / 'tests/fixtures/semantic_evidence_v1_original_reference.json'
        case = next(item for item in json.loads(original.read_text(encoding='utf-8'))['cases'] if item['id'] == case_id)
        request = project({k: v for k, v in case.items() if k != "expected"})
        expected = {"need": (SemanticSupportRelation(case["expected"]["relation"]), SemanticCoverage(case["expected"]["coverage"]))}
        return request, expected
    cases = adversarial_cases()
    manifest = json.loads((Path(__file__).resolve().parents[1] / "tests/hiring_case_review_freeze.json").read_text())
    if digest([asdict(item) for item in cases]) != manifest["adversarial-v1"]:
        raise ValueError("frozen_reference_changed")
    case = next(item for item in cases if item.case_id == "AV06")
    request = project({"id": "AV06", "source_refs": ["e0"], "confirmed_absence": False,
        "job_need": case.needs[0].text, "candidate_evidence": ["Traced a failed payment, isolated the cause, restored service and verified settlement."]})
    context = request.context
    fact = HardJobFact("tax-fact", "requirement", case.needs[1].text, "job-source")
    need = replace(context.job_profile.needs[0], need_id="tax", label=case.needs[1].text, hard_fact_refs=("tax-fact",))
    context = replace(context, hard_facts=replace(context.hard_facts, facts=(*context.hard_facts.facts, fact)),
        job_profile=replace(context.job_profile, needs=(*context.job_profile.needs, need)),
        source_registry=(*context.source_registry, RegisteredSourceRef("tax-fact", SourceRefClass.JOB_HARD_FACT, "job", "job_description")))
    return replace(request, context=context), {"need": (SemanticSupportRelation.DIRECT, SemanticCoverage.FULL),
                                             "tax": (SemanticSupportRelation.NONE, SemanticCoverage.NONE)}


def main(argv=None, *, config=None, transport_factory=None, output=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASE_IDS)
    parser.add_argument("--batch", choices=("batch-002",))
    parser.add_argument("--live", action="store_true", help="Requires configuration approval and separate confirmation.")
    parser.add_argument("--confirm-external-ai", action="store_true")
    args = parser.parse_args(argv)
    stream = output or sys.stdout
    def emit(value):
        print(json.dumps(value, sort_keys=True), file=stream, flush=True)
    ids = BATCH_002_IDS if args.batch else tuple(args.cases or CASE_IDS)
    maximum = 12 if args.batch else 8
    if (args.batch and args.cases) or len(ids) != len(set(ids)) or len(ids) > maximum:
        emit({"failure": "invalid_batch", "executed_requests": 0})
        return 2
    config = config if config is not None else read_semantic_shadow_config()
    adapter = OpenAISemanticEvidenceInterpreter(config, transport_factory=transport_factory)
    try:
        select = selected_batch_002_case if args.batch else selected_case
        cases = [(case_id, *select(case_id)) for case_id in ids]
        for _, request, _ in cases:
            adapter.prepare(request)
    except Exception:
        emit({"failure": "request_build_failed", "executed_requests": 0})
        return 2
    emit({"mode": "live_requested" if args.live else "dry_run", "planned_requests": len(cases),
          "case_ids": ids, "model": config.model or None, "feature_enabled": config.enabled,
          "max_requests": maximum, "max_output_tokens_per_request": 4096, "automatic_retries": 0,
          "batch": args.batch, "prompt_version": PROMPT_VERSION, "store": False,
          "input_tokens": None, "estimated_cost": None, "executed_requests": 0})
    if not args.live:
        return 0
    if not args.confirm_external_ai or not (args.cases or args.batch):
        emit({"failure": "not_authorized", "executed_requests": 0})
        return 2
    if not config.enabled or not config.model:
        emit({"failure": "disabled" if not config.enabled else "model_not_configured", "executed_requests": 0})
        return 2
    # No fallback, retry or auto-expansion. Stop the batch on the first failed request.
    for case_id, request, expected in cases:
        run = adapter.evaluate(request, allow_external_ai=True)
        emit({"case_id": case_id, **shadow_diagnostics(run),
              "comparisons": [asdict(item) for item in compare_semantic_shadow(run, expected)]})
        if run.failure is not None:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
