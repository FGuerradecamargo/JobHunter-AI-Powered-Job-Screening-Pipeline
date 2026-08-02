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
from services.database import (
    list_pending_candidate_jobs,
    save_candidate_job_analysis,
    update_shared_job_analysis_data,
)
from services.job_enricher import JobEnricher
from services.job_matcher import JobMatcher
from services.recommenders.recommendation_engine import (
    RecommendationEngine,
)


ANALYSIS_VERSION = "candidate-job-analysis-v3"
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
    return build_signature(
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "remote": job.remote,
            "salary": job.salary,
            "description": job.description,
            "url": job.url,
        }
    )


def build_candidate_signature(
    candidate,
) -> str:
    return build_signature(
        asdict(candidate)
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
        "below the candidate’s current level",
        "less technical than the candidate's current",
        "less technical than the candidate’s current",
        "career direction is more internal it desktop support",
        "not a direct match for the candidate's target",
        "not a direct match for the candidate’s target",
        "outside the candidate's target direction",
        "outside the candidate’s target direction",
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

        self.enricher = JobEnricher()
        self.matcher = JobMatcher()
        self.fit_analyzer = CandidateFitAnalyzer()

        self.recommendation_engine = (
            RecommendationEngine()
        )

        self.ai_service = AIRecommendationService(
            OpenAIClient()
        )

    def analyze_pending(
        self,
        candidate_id: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        candidate = self.candidate_repository.get(
            candidate_id
        )

        if candidate is None:
            raise ValueError(
                f"Candidate not found: {candidate_id}"
            )

        profile = candidate_to_profile(
            candidate
        )

        hard_filter = HardFilterAnalyzer(
            profile
        )

        candidate_signature = (
            build_candidate_signature(candidate)
        )

        pending_rows = list_pending_candidate_jobs(
            candidate_id=candidate_id,
            limit=limit,
        )

        result = {
            "selected": len(pending_rows),
            "analyzed": 0,
            "hard_rejected": 0,
            "matcher_rejected": 0,
            "ai_analyses_created": 0,
            "ai_approved": 0,
            "ai_rejected": 0,
            "descriptions_reused": 0,
            "descriptions_fetched": 0,
            "descriptions_failed": 0,
            "failed": 0,
            "errors": [],
        }

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

                hard_filter_result = (
                    hard_filter.analyze(job)
                )

                matcher_analysis = (
                    self.matcher.analyze(job)
                )

                job.score = matcher_analysis[
                    "score"
                ]

                job.reasons = matcher_analysis[
                    "reasons"
                ]

                job.classification = (
                    self.matcher.classify(job)
                )

                fit_analysis = (
                    self.fit_analyzer.analyze(
                        job,
                        profile,
                    )
                )

                deterministic_decision = (
                    self.recommendation_engine.recommend(
                        current_fit=fit_analysis[
                            "current_fit"
                        ],
                        growth_value=fit_analysis[
                            "growth_value"
                        ],
                    )
                )

                if hard_filter_result["rejected"]:
                    analysis = (
                        build_rule_rejection_analysis(
                            job=job,
                            reasons=hard_filter_result[
                                "reasons"
                            ],
                            matcher_analysis=(
                                matcher_analysis
                            ),
                            fit_analysis=fit_analysis,
                            rejection_type=(
                                "hard_filter"
                            ),
                        )
                    )

                    analysis_status = "rejected"

                    result["hard_rejected"] += 1

                elif (
                    job.classification
                    != self.matcher.RELEVANT
                ):
                    matcher_reasons = (
                        matcher_analysis["reasons"]
                        or [
                            (
                                "The role did not reach "
                                "the minimum relevance score."
                            )
                        ]
                    )

                    analysis = (
                        build_rule_rejection_analysis(
                            job=job,
                            reasons=matcher_reasons,
                            matcher_analysis=(
                                matcher_analysis
                            ),
                            fit_analysis=fit_analysis,
                            rejection_type="matcher",
                        )
                    )

                    analysis_status = "rejected"

                    result[
                        "matcher_rejected"
                    ] += 1

                else:
                    ai_analysis = (
                        self.ai_service.analyze(
                            job=job,
                            candidate_profile=profile,
                        )
                    )

                    analysis = asdict(
                        ai_analysis
                    )

                    analysis[
                        "deterministic_analysis"
                    ] = {
                        "score": matcher_analysis[
                            "score"
                        ],
                        "reasons": matcher_analysis[
                            "reasons"
                        ],
                        "classification": (
                            job.classification
                        ),
                        "current_fit": (
                            fit_analysis[
                                "current_fit"
                            ]
                        ),
                        "growth_value": (
                            fit_analysis[
                                "growth_value"
                            ]
                        ),
                        "current_fit_reasons": (
                            fit_analysis[
                                "current_fit_reasons"
                            ]
                        ),
                        "growth_reasons": (
                            fit_analysis[
                                "growth_reasons"
                            ]
                        ),
                        "recommendation": (
                            deterministic_decision[
                                "recommendation"
                            ]
                        ),
                        "recommendation_message": (
                            deterministic_decision[
                                "message"
                            ]
                        ),
                    }

                    result[
                        "ai_analyses_created"
                    ] += 1

                    if ai_analysis_should_be_visible(
                            analysis=analysis,
                            job=job,
                            candidate=candidate,
                    ):
                        analysis_status = "in_review"

                        result[
                            "ai_approved"
                        ] += 1
                    else:
                        analysis_status = "rejected"

                        result[
                            "ai_rejected"
                        ] += 1

                job_signature = (
                    build_job_signature(job)
                )

                save_candidate_job_analysis(
                    candidate_id=candidate_id,
                    job_id=job.id,
                    analysis=analysis,
                    job_signature=job_signature,
                    candidate_signature=(
                        candidate_signature
                    ),
                    analysis_version=(
                        ANALYSIS_VERSION
                    ),
                    status=analysis_status,
                )

                result["analyzed"] += 1

            except RateLimitError:
                result["failed"] += 1

                result["errors"].append(
                    {
                        "job_id": job.id,
                        "title": job.title,
                        "error": (
                            "OpenAI API quota unavailable."
                        ),
                    }
                )

                break

            except Exception as error:
                result["failed"] += 1

                result["errors"].append(
                    {
                        "job_id": job.id,
                        "title": job.title,
                        "error": str(error),
                    }
                )

        return result
