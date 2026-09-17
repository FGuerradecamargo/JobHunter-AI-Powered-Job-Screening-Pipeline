"""Synthetic reference cases, explicitly awaiting human review.

Expected labels are authored below before execution, never copied from the engine.
Only case facts are projected into legacy domain objects by the runner.
"""

from dataclasses import dataclass, replace
from enum import Enum


class RootCause(str, Enum):
    REQUIREMENT_EXTRACTION = "A_REQUIREMENT_EXTRACTION"
    EVIDENCE_LINKING = "B_EVIDENCE_LINKING"
    CAPABILITY_INTERPRETATION = "C_CAPABILITY_INTERPRETATION"
    OPPORTUNITY_VALUE = "D_OPPORTUNITY_VALUE"
    CLASSIFICATION_LOGIC = "E_CLASSIFICATION_LOGIC"
    INSUFFICIENT_DATA = "F_INSUFFICIENT_DATA"
    EXPECTED_CASE_NEEDS_REVIEW = "G_EXPECTED_CASE_NEEDS_REVIEW"


@dataclass(frozen=True)
class Need:
    key: str
    text: str
    importance: str
    question: str
    evidence_needed: str
    parsed_slot: str = ""


@dataclass(frozen=True)
class Proof:
    kind: str  # direct, transferable, absent, vague, confirmed_gap
    wording: str
    example: str
    source_available: bool = True


@dataclass(frozen=True)
class Capability:
    key: str
    exists: str  # yes, adjacent, no, plausible
    proof: Proof


@dataclass(frozen=True)
class CompanySide:
    family: str
    role: str
    needs: tuple[Need, ...]
    expected_work: str
    seniority_context: str
    eligibility_blocker: str = ""


@dataclass(frozen=True)
class CandidateContext:
    level: str
    scope: str
    severe_mismatch: bool = False


@dataclass(frozen=True)
class CandidateSide:
    capabilities: tuple[Capability, ...]
    context: CandidateContext


@dataclass(frozen=True)
class Compensation:
    annual_offer: int | None
    annual_current: int | None
    currency: str
    tradeoff: str


@dataclass(frozen=True)
class OpportunitySide:
    compensation: Compensation
    career_direction: str
    desired_family: str
    growth: str
    progression: str
    work_mode: str
    location: str
    remote_allowed: bool
    hybrid_allowed: bool
    onsite_allowed: bool
    role_content: str
    tradeoffs: str
    timing: str


@dataclass(frozen=True)
class CaseFacts:
    company: CompanySide
    candidate: CandidateSide
    opportunity: OpportunitySide


@dataclass(frozen=True)
class ExpectedReview:
    classification: str
    strength: str
    value: str
    states: tuple[tuple[str, str], ...]
    rationale: str


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    pair_id: str
    variant: str
    changed_path: str
    family: str
    facts: CaseFacts
    expected: ExpectedReview
    legacy_recommendation: str
    diagnostic_focus: RootCause
    review_track: str = "normative"
    human_review_status: str = "pending"


def expectation(label, strength, value, states, rationale):
    return ExpectedReview(label, strength, value, tuple(states.items()), rationale)


def _base(family, role, requirement, story):
    need = Need(
        "main", requirement, "core",
        f"Have you personally performed this work: {requirement.lower()}?",
        "A concrete case describing personal actions, methods, decisions and outcome.",
    )
    return CaseFacts(
        company=CompanySide(
            family, role, (need,), f"Own day-to-day {requirement.lower()} and explain decisions.",
            "Independent mid-level practitioner; supervised escalation for exceptional cases.",
        ),
        candidate=CandidateSide(
            (Capability("main", "yes", Proof("direct", requirement, story)),),
            CandidateContext("mid-level", "Independently performed the advertised scope."),
        ),
        opportunity=OpportunitySide(
            Compensation(None, None, "", "Salary undisclosed; no assumed pay advantage."),
            "The role is an explicit current target.", family,
            "Practice in the chosen direction; no promise of employer training.",
            "Lateral role at an appropriate level.", "remote", "Same country; no relocation.",
            True, True, False, "Target work is desirable.",
            "No known material cost beyond normal onboarding.",
            "Stable and selective; choose a role in the stated target direction.",
        ),
    )


def _proof(facts, proof, *, exists=None):
    original = facts.candidate.capabilities[0]
    changed = replace(original, proof=proof, exists=exists or original.exists)
    return replace(facts, candidate=replace(facts.candidate, capabilities=(changed, *facts.candidate.capabilities[1:])))


def _extra(facts, text, importance, proof, exists="yes"):
    need = Need(
        "extra", text, importance,
        f"Can you describe a real occasion when you personally did this: {text.lower()}?",
        "A source-backed example distinguishing independent work from assisted practice.",
    )
    return replace(
        facts, company=replace(facts.company, needs=(*facts.company.needs, need)),
        candidate=replace(facts.candidate, capabilities=(*facts.candidate.capabilities, Capability("extra", exists, proof))),
    )


def calibration_cases():
    cases = []

    def pair(number, a, b, path, ea, eb, legacy_a, legacy_b, cause, track="normative"):
        for variant, facts, expected, legacy in [("a", a, ea, legacy_a), ("b", b, eb, legacy_b)]:
            cases.append(CalibrationCase(
                f"HC{number:02d}{variant}", f"P{number:02d}", variant, path,
                facts.company.family, facts, expected, legacy, cause, track,
            ))

    a = _base("fraud_risk", "Fraud Investigator", "Investigate fraud patterns",
              "Reviewed linked payment events, compared device evidence, escalated the pattern and documented the disposition.")
    b = _proof(a, Proof("absent", "", "No investigation example is stored."))
    pair(1, a, b, "candidate.capabilities.0.proof",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Direct investigation evidence supports the target role."),
         expectation("worth_a_try", "viable", "high", {"main": "evidence_missing"}, "Capability is stated, but no case can yet support the CV or interview."),
         "best_match", "best_match", RootCause.CAPABILITY_INTERPRETATION)

    b = _proof(a, Proof("transferable", "Investigate fraud patterns",
                        "Investigated disputed purchases in customer operations using transaction trails; a defensible bridge, not fraud ownership."))
    pair(2, a, b, "candidate.capabilities.0.proof",
         expectation("best_match", "strong", "high", {"main": "proven"}, "The evidence directly matches investigator responsibilities."),
         expectation("worth_a_try", "viable", "high", {"main": "transferable"}, "Dispute investigation provides an adjacent bridge with domain limits."),
         "best_match", "potential", RootCause.CAPABILITY_INTERPRETATION)

    b = _proof(a, replace(a.candidate.capabilities[0].proof, wording="Investigated patterns of fraudulent payments"))
    pair(3, a, b, "candidate.capabilities.0.proof.wording",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Concrete investigation evidence supports the role."),
         expectation("best_match", "strong", "high", {"main": "proven"}, "Equivalent wording describes the same supported investigation, not less capability."),
         "best_match", "potential", RootCause.EVIDENCE_LINKING)

    a = _extra(a, "Write SQL investigation queries", "nice_to_have",
               Proof("confirmed_gap", "Write SQL investigation queries", "Candidate explicitly cannot write SQL queries independently."), "no")
    b = replace(a, company=replace(a.company, needs=(a.company.needs[0], replace(a.company.needs[1], importance="core"))))
    pair(4, a, b, "company.needs.1.importance",
         expectation("best_match", "strong", "high", {"main": "proven", "extra": "gap"}, "Investigation is proven and the SQL gap is peripheral."),
         expectation("worth_a_try", "weak", "high", {"main": "proven", "extra": "gap"}, "The same SQL gap now prevents independent core delivery."),
         "potential", "potential", RootCause.REQUIREMENT_EXTRACTION)

    a = _base("financial_crime_aml_kyc", "AML Analyst", "Review AML transaction alerts",
              "Investigated alerts against account history, recorded escalation reasons and passed a sampled quality review.")
    a = replace(a, opportunity=replace(a.opportunity, compensation=Compensation(72000, 60000, "EUR", "Material increase on the same annual basis; no added hours.")))
    b = replace(a, opportunity=replace(a.opportunity, compensation=Compensation(42000, 60000, "EUR", "Material pay reduction is unacceptable for a stable candidate; no offsetting benefit.")))
    pair(5, a, b, "opportunity.compensation",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Direct AML proof, target work and a meaningful pay improvement align."),
         expectation("youre_strong_but", "strong", "low", {"main": "proven"}, "Ability is unchanged; the specified pay sacrifice defeats personal value."),
         "best_match", "best_match", RootCause.OPPORTUNITY_VALUE)

    a = _base("financial_crime_aml_kyc", "KYC Reviewer", "Review corporate KYC files",
              "Checked beneficial ownership records, resolved documentary inconsistencies and delivered approved review files.")
    a = replace(a, opportunity=replace(a.opportunity, desired_family="fraud_risk", career_direction="A lateral bridge rather than the longer-term fraud target.",
                                       growth="No new skill scope is promised.", timing="Contract ends next month; immediate continuity is the explicit priority."))
    b = replace(a, opportunity=replace(a.opportunity, timing="Secure employment; no need for continuity and only a substantive progression is worthwhile."))
    pair(6, a, b, "opportunity.timing",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Proven KYC ability plus urgent income continuity justifies this lateral bridge."),
         expectation("youre_strong_but", "strong", "low", {"main": "proven"}, "A stable candidate gains no progression from the identical lateral role."),
         "good_opportunity", "good_opportunity", RootCause.OPPORTUNITY_VALUE)

    a = _base("financial_crime_aml_kyc", "Financial Crime Reviewer", "Document suspicious activity decisions",
              "Assembled chronology, separated facts from suspicion, documented the decision and incorporated compliance review feedback.")
    b = _proof(a, Proof("vague", "Document suspicious activity decisions", "Claims familiarity but cannot provide any personal decision, action or outcome."))
    pair(7, a, b, "candidate.capabilities.0.proof",
         expectation("best_match", "strong", "high", {"main": "proven"}, "A concrete defensible decision record supports a safe CV claim."),
         expectation("worth_a_try", "viable", "high", {"main": "evidence_missing"}, "A matching skill label alone is not usable proof, even inside an experience record."),
         "best_match", "best_match", RootCause.CAPABILITY_INTERPRETATION)

    a = _base("customer_operations", "Customer Operations Specialist", "Resolve complex escalations",
              "Reconstructed a failed-service timeline, coordinated a correction and confirmed resolution with the customer.")
    b = replace(a, company=replace(a.company, eligibility_blocker="Mandatory relocation conflicts with confirmed inability to relocate."))
    pair(8, a, b, "company.eligibility_blocker",
         expectation("best_match", "strong", "high", {"main": "proven"}, "The target escalation role is feasible and supported."),
         expectation("ineligible", "ineligible", "high", {"main": "proven"}, "Mandatory relocation is an upstream blocker regardless of fit or attractiveness."),
         "best_match", "reject", RootCause.CLASSIFICATION_LOGIC)

    b = replace(a, opportunity=replace(a.opportunity, role_content="Explicitly avoid: Resolve complex escalations"))
    pair(9, a, b, "opportunity.role_content",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Supported work also matches the candidate's content preference."),
         expectation("youre_strong_but", "strong", "low", {"main": "proven"}, "The candidate can do the work but explicitly wants to stop doing it."),
         "best_match", "good_opportunity", RootCause.OPPORTUNITY_VALUE)

    a = _base("technical_support", "Technical Support Engineer", "Diagnose application incidents",
              "Reproduced a service failure, inspected logs, isolated a configuration fault and verified recovery.")
    b = replace(a, candidate=replace(a.candidate, context=CandidateContext("junior", "Only works under close supervision; cannot independently own the advertised incident scope.", True)))
    pair(10, a, b, "candidate.context",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Independent incident delivery matches company scope."),
         expectation("worth_a_try", "weak", "high", {"main": "proven"}, "Real examples exist, but the independent seniority/context demand is not met."),
         "best_match", "potential", RootCause.CAPABILITY_INTERPRETATION)

    a = _extra(a, "Query production logs with SQL", "core",
               Proof("confirmed_gap", "Query production logs with SQL", "Candidate confirms SQL log querying cannot yet be performed."), "no")
    a = replace(a, opportunity=replace(a.opportunity, role_content="Explicitly avoid: Diagnose application incidents"))
    b = replace(a, company=replace(a.company, needs=(a.company.needs[0], replace(a.company.needs[1], parsed_slot="tools_and_technologies"))))
    pair(11, a, b, "company.needs.1.parsed_slot",
         expectation("skip_for_now", "weak", "low", {"main": "proven", "extra": "gap"}, "Independent SQL investigation is a core gap and the candidate explicitly avoids this work."),
         expectation("skip_for_now", "weak", "low", {"main": "proven", "extra": "gap"}, "A parser storing an unwanted role's core tool in a generic tools list must not reduce its materiality."),
         "potential", "potential", RootCause.REQUIREMENT_EXTRACTION)

    a = _base("technical_support", "Support Specialist", "Reproduce software defects",
              "Produced a minimal reproduction, captured logs and validated the release containing the fix.")
    b = _proof(a, replace(a.candidate.capabilities[0].proof, source_available=False))
    pair(12, a, b, "candidate.capabilities.0.proof.source_available",
         expectation("best_match", "strong", "high", {"main": "proven"}, "The reproducible defect example supports the target role."),
         expectation("worth_a_try", "viable", "high", {"main": "evidence_missing"}, "Reviewed: the example exists but its source ID was lost. Repair provenance; this is not a capability gap or a request for new evidence."),
         "best_match", "potential", RootCause.INSUFFICIENT_DATA)

    a = _base("technical_operations", "Technical Operations Analyst", "Restore failed scheduled jobs",
              "Identified a failed dependency, used the recovery runbook and verified downstream data completeness.")
    b = replace(a, company=replace(a.company, eligibility_blocker="Mandatory night shift conflicts with a confirmed non-negotiable scheduling constraint."))
    pair(13, a, b, "company.eligibility_blocker",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Supported recovery work fits the candidate's direction."),
         expectation("ineligible", "ineligible", "high", {"main": "proven"}, "The hard scheduling conflict overrides the otherwise strong case."),
         "best_match", "reject", RootCause.CLASSIFICATION_LOGIC)

    b = replace(a, opportunity=replace(a.opportunity, desired_family="business_analysis"))
    pair(14, a, b, "opportunity.desired_family",
         expectation("best_match", "strong", "high", {"main": "proven"}, "The role is in the candidate's current chosen family."),
         expectation("youre_strong_but", "strong", "medium", {"main": "proven"}, "A capable lateral fallback has limited value relative to the new analysis target."),
         "best_match", "good_opportunity", RootCause.OPPORTUNITY_VALUE)

    a = _base("business_analysis", "Business Analyst", "Map operational requirements",
              "Interviewed process owners, mapped handoffs, reconciled conflicting needs and obtained sign-off on acceptance criteria.")
    a = _extra(a, "Coordinate cross-functional delivery", "important",
               Proof("direct", "Coordinate cross-functional delivery", "Tracked dependencies, negotiated scope and secured acceptance across business and engineering."))
    b = replace(a, candidate=replace(a.candidate, capabilities=(a.candidate.capabilities[0], replace(
        a.candidate.capabilities[1], proof=Proof("transferable", "Coordinate cross-functional delivery", "Coordinated support escalations between teams but did not own project delivery.")))))
    pair(15, a, b, "candidate.capabilities.1.proof",
         expectation("best_match", "strong", "high", {"main": "proven", "extra": "proven"}, "Requirements work and important delivery responsibilities are directly evidenced."),
         expectation("best_match", "strong", "high", {"main": "proven", "extra": "transferable"}, "Reviewed: defensible transferable IMPORTANT evidence does not downgrade proven CORE delivery; direct ownership was not mandatory. Preserve adjacent scope in representation."),
         "best_match", "potential", RootCause.CLASSIFICATION_LOGIC)

    a = _base("business_analysis", "Process Analyst", "Map operational requirements",
              "Observed workflow, modeled decision points, validated exceptions and documented agreed process changes.")
    b = replace(a, company=replace(a.company, needs=(replace(a.company.needs[0], parsed_slot="important_details"),)))
    pair(16, a, b, "company.needs.0.parsed_slot",
         expectation("best_match", "strong", "high", {"main": "proven"}, "An explicit core need and direct proof make a strong case."),
         expectation("best_match", "strong", "high", {"main": "proven"}, "The same core need remains real when the parsed profile puts it in unstructured important details."),
         "best_match", "best_match", RootCause.REQUIREMENT_EXTRACTION)

    a = _base("operations_management", "Operations Manager", "Lead operational teams",
              "Planned shift coverage, reviewed quality exceptions, coached staff and restored service targets.")
    a = replace(a, company=replace(a.company, seniority_context="Manage multiple sites through team leads; accountable for staffing and operational controls."),
                candidate=replace(a.candidate, context=CandidateContext("manager", "Previously managed comparable multi-site staffing and controls.")))
    b = replace(a, candidate=replace(a.candidate, context=CandidateContext("team lead", "Only led one small shift; no manager-of-managers or multi-site accountability.", True)))
    pair(17, a, b, "candidate.context",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Real leadership evidence and comparable scale support this management role."),
         expectation("worth_a_try", "weak", "high", {"main": "proven"}, "A genuine team-leading example does not prove the required management scale."),
         "best_match", "potential", RootCause.CAPABILITY_INTERPRETATION)

    a = _base("operations_management", "Operations Team Lead", "Lead operational teams",
              "Allocated work, coached colleagues and coordinated recovery from a missed service target.")
    a = replace(a, opportunity=replace(a.opportunity, progression="Hands-on team leadership; useful advancement only below department-head level."),
                candidate=replace(a.candidate, context=CandidateContext("senior specialist", "Ready for the first formal team-lead position.")))
    b = replace(a, candidate=replace(a.candidate, context=CandidateContext("department head", "Already owns several teams and seeks strategic scope; this role is substantial down-leveling.")))
    pair(18, a, b, "candidate.context",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Evidenced leadership and first formal progression make this valuable."),
         expectation("youre_strong_but", "strong", "low", {"main": "proven"}, "Overqualification does not erase ability, but the role sacrifices the stated strategic scope."),
         "best_match", "competitive", RootCause.OPPORTUNITY_VALUE)

    a = _base("customer_success", "Customer Success Manager", "Plan customer adoption",
              "Mapped customer objectives, agreed an adoption plan, monitored use and adjusted it after a stakeholder review.")
    a = replace(a, opportunity=replace(a.opportunity, desired_family="business_analysis", career_direction="A lateral fallback while considering business analysis.", growth="No specific growth advantage is known."))
    b = replace(a, opportunity=replace(a.opportunity, compensation=Compensation(90000, 60000, "EUR", "The candidate explicitly accepts the lateral role for this annual pay improvement; hours are unchanged.")))
    pair(19, a, b, "opportunity.compensation",
         expectation("youre_strong_but", "strong", "medium", {"main": "proven"}, "Unknown salary is not a penalty; this otherwise lateral option has only uncertain upside."),
         expectation("best_match", "strong", "high", {"main": "proven"}, "The known and explicitly valued salary improvement makes the same supported role attractive."),
         "good_opportunity", "good_opportunity", RootCause.OPPORTUNITY_VALUE)

    a = _base("customer_success", "Customer Success Manager", "Plan customer adoption",
              "Defined an adoption milestone, coached customer owners and reviewed progress against the agreed plan.")
    a = replace(a, opportunity=replace(a.opportunity, location="Office commute cost not yet established.",
                                       tradeoffs="Hybrid is allowed, but its personal cost is not yet known."))
    b = replace(a, opportunity=replace(a.opportunity, work_mode="hybrid"))
    pair(20, a, b, "opportunity.work_mode",
         expectation("best_match", "strong", "high", {"main": "proven"}, "Remote target work appears valuable; confirm remaining conditions before accepting."),
         expectation("best_match", "strong", "high", {"main": "proven"}, "Reviewed: acceptable hybrid with unknown commute cost retains HIGH value, with reduced confidence. Uncertainty changes confidence before valence."),
         "best_match", "best_match", RootCause.EXPECTED_CASE_NEEDS_REVIEW, "exploratory")

    reviewed = {"HC12b", "HC15b", "HC20b"}
    return tuple(replace(case, human_review_status="reviewed") if case.case_id in reviewed else case for case in cases)
