from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import time
from dataclasses import asdict
from typing import Any

from openai import RateLimitError

from models.job import Job
from services.ai.ai_recommendation_service import (
    AIRecommendationService,
)
from services.ai.openai_client import OpenAIClient
from services.analysis_signatures import (
    build_job_signature as build_shared_job_signature,
)
from services.analyzers.candidate_fit_analyzer import (
    CandidateFitAnalyzer,
)
from services.analyzers.hard_filter_analyzer import (
    HardFilterAnalyzer,
)
from services.candidate_adapter import (
    candidate_to_profile,
)
from services.candidate_repository import (
    CandidateRepository,
)
from services.career_objective_repository import (
    CareerObjectiveRepository,
)
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.database import (
    list_pending_candidate_jobs,
    save_candidate_job_analysis,
    update_shared_job_analysis_data,
)
from services.job_enricher import JobEnricher
from services.job_profile_manager import JobProfileManager
from services.ai.job_profile_service import JobProfileService
from services.job_matcher import JobMatcher
from services.job_bucket_classifier import (
    classify_job_bucket,
    BEST_MATCH,
    TRADEOFF,
    REJECT,
)
from services.recommenders.recommendation_engine import (
    RecommendationEngine,
)


from services.ai_usage_budget import AIUsageBudget

ANALYSIS_VERSION = "candidate-job-analysis-v15"
REQUEST_DELAY_SECONDS = 2


AI_VISIBLE_RECOMMENDATIONS = {
    "recommended_apply",
    "worth_second_look",
}

AI_VISIBLE_COMPETITIVE_STATUSES = {
    "competitive_now",
    "bridge_opportunity",
}


def build_signature(
    data: dict[str, Any],
) -> str:
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def row_to_job(
    row: dict[str, Any],
) -> Job:
    remote_value = row.get("remote")

    if remote_value is None:
        remote = None
    else:
        remote = bool(remote_value)

    return Job(
        id=str(row["id"]),
        raw_text=row.get("raw_text") or "",
        url=row.get("url") or "",
        title=row.get("title"),
        company=row.get("company"),
        location=row.get("location"),
        remote=remote,
        salary=row.get("salary"),
        easy_apply=bool(
            row.get("easy_apply", False)
        ),
        description=row.get("description"),
    )


def build_job_signature(
    job: Job,
) -> str:
    return build_shared_job_signature(job)


def build_candidate_signature(
    candidate,
    career_objective=None,
    career_updates=None,
) -> str:
    data = {
        "candidate": asdict(candidate),
        "career_updates": [
            asdict(update)
            for update in (
                career_updates or []
            )
        ],
    }

    if career_objective is not None:
        data["career_objective"] = asdict(
            career_objective
        )

    return build_signature(
        data
    )


def build_rule_rejection_analysis(
    job: Job,
    reasons: list[str],
    matcher_analysis: dict[str, Any],
    fit_analysis: dict[str, Any],
    rejection_type: str,
) -> dict[str, Any]:
    rejection_reasons = reasons or [
        "The role did not pass automated screening."
    ]

    return {
        "job_id": job.id,
        "recommendation": "not_competitive_now",
        "competitive_status": "not_competitive_now",
        "current_fit": fit_analysis["current_fit"],
        "growth_value": fit_analysis["growth_value"],
        "job_level": "",
        "candidate_level": "",
        "level_assessment": (
            "The role was removed during automated "
            "rule-based screening."
        ),
        "core_requirements": [],
        "requirements_met": [],
        "strengths": fit_analysis[
            "current_fit_reasons"
        ],
        "development_gaps": fit_analysis[
            "growth_reasons"
        ],
        "structural_gaps": rejection_reasons,
        "positive_points": [],
        "personal_negatives": [],
        "hard_conflicts": (
            rejection_reasons
            if rejection_type == "hard_filter"
            else []
        ),
        "reason": rejection_reasons[0],
        "final_reason": (
            "This role was removed during automated "
            "rule-based screening and was not sent to AI."
        ),
        "rule_rejection_type": rejection_type,
        "deterministic_analysis": {
            "score": matcher_analysis["score"],
            "reasons": matcher_analysis["reasons"],
            "classification": job.classification,
            "current_fit": fit_analysis[
                "current_fit"
            ],
            "growth_value": fit_analysis[
                "growth_value"
            ],
            "current_fit_reasons": fit_analysis[
                "current_fit_reasons"
            ],
            "growth_reasons": fit_analysis[
                "growth_reasons"
            ],
        },
    }


def ai_analysis_should_be_visible(
    analysis: dict[str, Any],
    job: Job,
    candidate,
) -> bool:
    recommendation = analysis.get(
        "recommendation"
    )

    competitive_status = analysis.get(
        "competitive_status"
    )

    current_fit = analysis.get(
        "current_fit"
    ) or 0

    growth_value = analysis.get(
        "growth_value"
    ) or 0

    hard_conflicts = analysis.get(
        "hard_conflicts"
    ) or []

    personal_negatives = analysis.get(
        "personal_negatives"
    ) or []

    structural_gaps = analysis.get(
        "structural_gaps"
    ) or []

    reason = analysis.get(
        "reason"
    ) or ""

    final_reason = analysis.get(
        "final_reason"
    ) or ""

    review_text = " ".join(
        [
            *personal_negatives,
            *structural_gaps,
            reason,
            final_reason,
        ]
    ).lower()

    if hard_conflicts:
        return False

    if competitive_status not in {
        "competitive_now",
        "bridge_opportunity",
    }:
        return False

    if recommendation == "recommended_apply":
        minimum_scores_passed = (
            current_fit >= 60
            and growth_value >= 40
        )

    elif recommendation == "worth_second_look":
        minimum_scores_passed = (
            current_fit >= 65
            and growth_value >= 60
        )

    else:
        return False

    if not minimum_scores_passed:
        return False

    preferences = candidate.preferences
    constraints = candidate.constraints

    fully_onsite_signals = {
        "fully onsite",
        "fully on-site",
        "full onsite",
        "full on-site",
        "five days onsite",
        "five days on-site",
    }

    if (
        not preferences.onsite_allowed
        and any(
            signal in review_text
            for signal in fully_onsite_signals
        )
    ):
        return False

    phone_heavy_signals = {
        "high-volume inbound",
        "high volume inbound",
        "phone-heavy",
        "phone heavy",
        "contact-centre",
        "contact centre",
        "call-centre",
        "call centre",
    }

    if (
        preferences.phone_support_preference
        == "limited"
        and any(
            signal in review_text
            for signal in phone_heavy_signals
        )
    ):
        return False

    customer_heavy_signals = {
        "high external customer interaction",
        "external customer interaction is central",
        "primary customer contact",
        "high-volume external customer support",
        "high volume external customer support",
    }

    if (
        preferences.customer_facing_preference
        == "limited"
        and any(
            signal in review_text
            for signal in customer_heavy_signals
        )
    ):
        return False

    night_or_on_call_signals = {
        "overnight on-call is required",
        "overnight on call is required",
        "night shift is required",
        "night shifts are required",
        "24/7 on-call requirement",
        "24/7 on call requirement",
    }

    if (
        constraints.night_shift_is_blocking
        and any(
            signal in review_text
            for signal in night_or_on_call_signals
        )
    ):
        return False

    career_regression_signals = {
        "step down",
        "downlevel",
        "below the candidate's current level",
        "below the candidateâ€™s current level",
        "less technical than the candidate's current",
        "less technical than the candidateâ€™s current",
        "career direction is more internal it desktop support",
        "not a direct match for the candidate's target",
        "not a direct match for the candidateâ€™s target",
        "outside the candidate's target direction",
        "outside the candidateâ€™s target direction",
    }

    if any(
        signal in review_text
        for signal in career_regression_signals
    ):
        return False

    mandatory_relocation_signals = {
        "mandatory relocation",
        "relocation is required",
        "must relocate",
    }

    if (
        constraints.mandatory_relocation_is_blocking
        and any(
            signal in review_text
            for signal in mandatory_relocation_signals
        )
    ):
        return False

    return True


class CandidateJobAnalysisService:
    def __init__(self) -> None:
        self.candidate_repository = (
            CandidateRepository()
        )

        self.career_objective_repository = (
            CareerObjectiveRepository()
        )
        self.career_update_repository = (
            CareerUpdateRepository()
        )

        self.enricher = JobEnricher()
        self.matcher = JobMatcher()
        self.fit_analyzer = CandidateFitAnalyzer()

        self.recommendation_engine = (
            RecommendationEngine()
        )

        self.ai_service = AIRecommendationService(
            OpenAIClient()
        )

        self.job_profile_manager = JobProfileManager(
            JobProfileService(
                OpenAIClient()
            )
        )

    def analyze_pending(
        self,
        candidate_id: str,
        limit: int = 5,
        target_opportunities: int | None = None,
        ai_budget: AIUsageBudget | None = None,
    ) -> dict[str, Any]:
        candidate = self.candidate_repository.get(
            candidate_id
        )

        if candidate is None:
            raise ValueError(
                f"Candidate not found: {candidate_id}"
            )

        career_objective = (
            self.career_objective_repository
            .get_active(candidate_id)
        )

        career_updates = (
            self.career_update_repository
            .list_for_candidate(candidate_id)
        )

        profile = candidate_to_profile(
            candidate,
            career_objective,
            career_updates,
        )

        hard_filter = HardFilterAnalyzer(
            profile
        )

        candidate_signature = (
            build_candidate_signature(
                candidate,
                career_objective,
                career_updates,
            )
        )

        pending_rows = list_pending_candidate_jobs(
            candidate_id=candidate_id,
            limit=limit,
            analysis_version=ANALYSIS_VERSION,
            candidate_signature=candidate_signature,
        )

        result = {
            "selected": len(pending_rows),
            "analyzed": 0,
            "hard_rejected": 0,
            "ai_eligible": 0,
            "ai_analyses_created": 0,
            "ai_approved": 0,
            "ai_rejected": 0,
            "best_match": 0,
            "potential": 0,
            "good_opportunity": 0,

            "opportunities_found": 0,
            "target_reached": False,
            "usage_limit_reached": False,
            "provider_quota_exhausted": False,

            "descriptions_reused": 0,
            "descriptions_fetched": 0,
            "descriptions_failed": 0,
            "failed": 0,
            "errors": [],

            "batch_market_signals": [],
            "batch_ai_job_ids": [],
        }

        ai_queue: list[dict[str, Any]] = []

        # =============================================
        # PHASE 1
        # Enrich -> Job Profile -> Hard Filter
        # =============================================

        for row in pending_rows:
            job = row_to_job(row)

            try:
                if job.description:
                    result[
                        "descriptions_reused"
                    ] += 1

                else:
                    self.enricher.enrich(job)

                    if job.description:
                        result[
                            "descriptions_fetched"
                        ] += 1

                        update_shared_job_analysis_data(
                            job
                        )

                    else:
                        result[
                            "descriptions_failed"
                        ] += 1

                    time.sleep(
                        REQUEST_DELAY_SECONDS
                    )

                job_profile = (
                    self.job_profile_manager
                    .get_or_create(job)
                )

                hard_filter_result = (
                    hard_filter.analyze(
                        job,
                        job_profile,
                    )
                )

                if hard_filter_result["rejected"]:
                    rejection_reasons = (
                        hard_filter_result["reasons"]
                        or [
                            "The role failed a hard constraint."
                        ]
                    )

                    analysis = {
                        "job_id": job.id,
                        "recommendation": "reject",
                        "competitive_status": (
                            "not_competitive_now"
                        ),
                        "current_fit": 0,
                        "growth_value": 0,
                        "direction_alignment": "low",
                        "job_level": (
                            job_profile.seniority
                        ),
                        "candidate_level": "",
                        "level_assessment": "",
                        "core_requirements": (
                            job_profile
                            .must_have_capabilities
                        ),
                        "requirements_met": [],
                        "strengths": [],
                        "development_gaps": [],
                        "structural_gaps": (
                            rejection_reasons
                        ),
                        "positive_points": [],
                        "personal_negatives": [],
                        "priority_matches": [],
                        "priority_conflicts": [],
                        "hard_conflicts": (
                            rejection_reasons
                        ),
                        "reason": (
                            rejection_reasons[0]
                        ),
                        "final_reason": (
                            "Rejected by a hard "
                            "constraint before candidate "
                            "AI analysis."
                        ),
                        "simple_summary": (
                            job_profile.summary
                        ),
                        "simple_recommendation": (
                            "Reject. A hard constraint "
                            "blocks this opportunity."
                        ),
                        "tailored_cv": None,
                        "interview_prep": None,
                        "bucket": "reject",
                        "rule_rejection_type": (
                            "hard_filter"
                        ),
                    }

                    save_candidate_job_analysis(
                        candidate_id=candidate_id,
                        job_id=job.id,
                        analysis=analysis,
                        job_signature=(
                            build_job_signature(job)
                        ),
                        candidate_signature=(
                            candidate_signature
                        ),
                        analysis_version=(
                            ANALYSIS_VERSION
                        ),
                        status="system_rejected",
                    )

                    result["hard_rejected"] += 1
                    result["analyzed"] += 1

                    continue

                ai_queue.append(
                    {
                        "job": job,
                        "job_profile": job_profile,
                    }
                )

            except Exception as error:
                result["failed"] += 1

                result["errors"].append(
                    {
                        "job_id": job.id,
                        "title": job.title,
                        "error": str(error),
                    }
                )

        result["ai_eligible"] = len(
            ai_queue
        )

        if not ai_queue:
            return result

        # =============================================
        # PHASE 2
        # Candidate-specific AI comparison
        #
        # Run in small waves so we do not spend AI calls
        # after the requested opportunity target is met.
        # =============================================

        def analyze_with_ai(
            item: dict[str, Any],
        ):
            job = item["job"]
            job_profile = item["job_profile"]

            ai_analysis = (
                self.ai_service.analyze(
                    job=job,
                    job_profile=job_profile,
                    candidate_profile=profile,
                )
            )

            return item, ai_analysis

        queue_index = 0
        opportunities_found = 0

        while queue_index < len(ai_queue):
            if (
                target_opportunities is not None
                and opportunities_found
                >= target_opportunities
            ):
                break

            if (
                ai_budget is not None
                and ai_budget.exhausted
            ):
                result[
                    "usage_limit_reached"
                ] = True

                break

            remaining_jobs = (
                len(ai_queue)
                - queue_index
            )

            wave_size = min(
                4,
                remaining_jobs,
            )

            if target_opportunities is not None:
                remaining_target = max(
                    1,
                    target_opportunities
                    - opportunities_found,
                )

                wave_size = min(
                    wave_size,
                    remaining_target,
                )

            if (
                ai_budget is not None
                and ai_budget.remaining is not None
            ):
                wave_size = min(
                    wave_size,
                    ai_budget.remaining,
                )

            if wave_size <= 0:
                result[
                    "usage_limit_reached"
                ] = True

                break

            wave = ai_queue[
                queue_index:
                queue_index + wave_size
            ]

            queue_index += wave_size

            provider_quota_exhausted = False

            with ThreadPoolExecutor(
                max_workers=wave_size
            ) as executor:
                futures = {
                    executor.submit(
                        analyze_with_ai,
                        item,
                    ): item
                    for item in wave
                }

                for future in as_completed(futures):
                    item = futures[future]
                    job = item["job"]

                    try:
                        _, ai_analysis = (
                            future.result()
                        )

                        # The AI call happened. Count it even
                        # if persistence later fails.
                        if ai_budget is not None:
                            ai_budget.consume()

                        analysis = asdict(
                            ai_analysis
                        )

                        bucket = analysis.get(
                            "recommendation",
                            "reject",
                        )

                        if bucket not in {
                            "best_match",
                            "potential",
                            "good_opportunity",
                            "reject",
                        }:
                            bucket = "reject"

                        analysis["bucket"] = bucket

                        market_signal = analysis.get(
                            "market_signal"
                        )

                        if market_signal:
                            result[
                                "batch_market_signals"
                            ].append(
                                {
                                    "job_id": job.id,
                                    "recommendation": bucket,
                                    "current_fit": (
                                        analysis.get(
                                            "current_fit",
                                            0,
                                        )
                                    ),
                                    "market_signal": (
                                        market_signal
                                    ),
                                }
                            )

                        result[
                            "batch_ai_job_ids"
                        ].append(job.id)

                        result[
                            "ai_analyses_created"
                        ] += 1

                        if bucket == "best_match":
                            analysis_status = (
                                "in_review"
                            )

                            result[
                                "best_match"
                            ] += 1

                            result[
                                "ai_approved"
                            ] += 1

                            opportunities_found += 1

                        elif bucket == "potential":
                            analysis_status = (
                                "in_review"
                            )

                            result[
                                "potential"
                            ] += 1

                            result[
                                "ai_approved"
                            ] += 1

                            opportunities_found += 1

                        elif bucket == "good_opportunity":
                            analysis_status = (
                                "in_review"
                            )

                            result[
                                "good_opportunity"
                            ] += 1

                            result[
                                "ai_approved"
                            ] += 1

                            opportunities_found += 1

                        else:
                            analysis_status = (
                                "system_rejected"
                            )

                            analysis[
                                "tailored_cv"
                            ] = None

                            analysis[
                                "interview_prep"
                            ] = None

                            result[
                                "ai_rejected"
                            ] += 1

                        save_candidate_job_analysis(
                            candidate_id=candidate_id,
                            job_id=job.id,
                            analysis=analysis,
                            job_signature=(
                                build_job_signature(job)
                            ),
                            candidate_signature=(
                                candidate_signature
                            ),
                            analysis_version=(
                                ANALYSIS_VERSION
                            ),
                            status=analysis_status,
                        )

                        result[
                            "analyzed"
                        ] += 1

                    except RateLimitError:
                        result["failed"] += 1

                        result[
                            "provider_quota_exhausted"
                        ] = True

                        result["errors"].append(
                            {
                                "job_id": job.id,
                                "title": job.title,
                                "error": (
                                    "OpenAI API quota "
                                    "unavailable."
                                ),
                            }
                        )

                        provider_quota_exhausted = True

                    except Exception as error:
                        result["failed"] += 1

                        result["errors"].append(
                            {
                                "job_id": job.id,
                                "title": job.title,
                                "error": str(error),
                            }
                        )

            if provider_quota_exhausted:
                break

        result[
            "opportunities_found"
        ] = result["ai_approved"]

        if target_opportunities is not None:
            result[
                "target_reached"
            ] = (
                result["opportunities_found"]
                >= target_opportunities
            )

        if (
            ai_budget is not None
            and ai_budget.exhausted
            and not result["target_reached"]
        ):
            result[
                "usage_limit_reached"
            ] = True

        return result

