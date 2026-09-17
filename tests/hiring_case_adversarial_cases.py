"""adversarial-v1: proposed judgments authored before execution, not human gold.

Raw facts, expected judgments and hostile/hypothetical provider replies are separate.
No engine imports. Never derive expectations from observed results.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NeedFacts:
    text: str = "Resolve payment incidents independently"
    importance: str = "core"
    evidence: str = "Traced a failed payment, isolated the cause, restored service and verified settlement."
    source_available: bool = True
    transferable: bool = False
    confirmed_gap: bool = False
    authority: str = "explicit"
    direct_required: bool = False


@dataclass(frozen=True)
class Expected:
    classification: str
    strength: str
    value: str
    states: tuple[str, ...]
    rationale: str
    confidence: str = "medium"


@dataclass(frozen=True)
class Reply:
    states: tuple[str, ...]
    value: str = "positive"
    dimension: str = "career_direction"
    inferred_blocker: bool = False
    checkpoint_ref: bool = False
    reuse_first_ref: bool = False


@dataclass(frozen=True)
class AdversarialCase:
    case_id: str
    scenario: str
    company: str
    candidate: str
    opportunity: str
    needs: tuple[NeedFacts, ...]
    expected: Expected
    reply: Reply
    taxonomy: str = "none"
    known_value_fact: bool = True
    hard_blocker: bool = False
    scope_mismatch: bool = False


P = NeedFacts()
T = NeedFacts("Coordinate release communications", "important",
              "Coordinated support escalations across teams, not release ownership.", transferable=True)
G = NeedFacts("Use optional diagram tooling", "nice_to_have", "Explicitly cannot use this tool.", confirmed_gap=True)


def adversarial_cases():
    return (
        AdversarialCase("AV01", "several important bridges", "Core incident recovery; release and vendor coordination important.",
            "Independent recovery with defensible adjacent coordination in both secondary areas.", "Chosen target work.",
            (P, T, NeedFacts("Coordinate vendors", "important", "Coordinated external support, not procurement.", transferable=True)),
            Expected("best_match", "strong", "high", ("proven", "transferable", "transferable"), "Reviewed B: important bridges do not automatically downgrade proven core."),
            Reply(("proven", "transferable", "transferable"))),
        AdversarialCase("AV02", "explicit direct ownership constraint", "Secondary IMPORTANT release role explicitly requires prior independent release ownership.",
            "Core incidents proven; only adjacent release coordination.", "Target role.",
            (P, NeedFacts("Own releases directly", "important", "Supported release communications, never owned release.", transferable=True, direct_required=True)),
            Expected("worth_a_try", "viable", "high", ("proven", "transferable"), "Explicit direct-ownership condition matters; IMPORTANT alone does not express it."),
            Reply(("proven", "transferable")), "unsupported_direct_evidence_constraint"),
        AdversarialCase("AV03", "multiple peripheral gaps", "Recovery core; optional diagram and reporting tools.",
            "Core recovery proven; explicitly lacks both optional tools.", "Aligned target.", (P, G, NeedFacts("Optional report tool", "nice_to_have", "Confirmed no use.", confirmed_gap=True)),
            Expected("best_match", "strong", "high", ("proven", "gap", "gap"), "Peripheral confirmed gaps do not defeat core proof."), Reply(("proven", "gap", "gap"))),
        AdversarialCase("AV04", "broken source", "Independent incident recovery.", "Detailed recovery record exists; import lost its authoritative ID.", "Target work.",
            (NeedFacts(source_available=False),), Expected("worth_a_try", "viable", "high", ("evidence_missing",), "Reviewed A: repair provenance, not candidate capability."), Reply(("proven",))),
        AdversarialCase("AV05", "irrelevant valid evidence", "Own incident recovery.", "Only wrote office lunch rota; valid source ID.", "Target work.",
            (NeedFacts(evidence="Organized lunch rota; no incident recovery."),),
            Expected("worth_a_try", "viable", "high", ("evidence_missing",), "Provenance cannot make irrelevant evidence support recovery."), Reply(("proven",)), "semantic_entailment"),
        AdversarialCase("AV06", "unrelated evidence reuse", "Recovery and tax filing both CORE.", "Recovery documented; no tax work. Provider reuses the recovery record.", "Target role.",
            (P, NeedFacts("File regulated tax returns", evidence="No tax filing example.")),
            Expected("worth_a_try", "viable", "high", ("proven", "evidence_missing"), "Same source cannot prove unrelated tax delivery."), Reply(("proven", "proven"), reuse_first_ref=True), "semantic_entailment"),
        AdversarialCase("AV07", "strong but poor value", "Supported recovery work, known pay below non-negotiable target.", "Core proven; cannot accept pay reduction.", "EUR 30k offered against EUR 55k minimum.", (P,),
            Expected("youre_strong_but", "strong", "low", ("proven",), "Known material negative cost is independent of ability."), Reply(("proven",), "negative", "compensation")),
        AdversarialCase("AV08", "weak but attractive", "Independent recovery is core.", "Explicitly unable to recover incidents independently.", "Excellent aligned training opportunity, not proof of readiness.",
            (NeedFacts(evidence="User confirmed cannot perform independent recovery.", confirmed_gap=True),),
            Expected("worth_a_try", "weak", "high", ("gap",), "Attractive value does not repair a confirmed core gap."), Reply(("gap",))),
        AdversarialCase("AV09", "unknown salary", "Salary undisclosed.", "Core proven, no salary fact.", "No other established value advantage.", (P,),
            Expected("youre_strong_but", "strong", "medium", ("proven",), "Unknown salary is not negative or positive.", "low"), Reply(("proven",), "negative", "compensation"), known_value_fact=False),
        AdversarialCase("AV10", "below target", "EUR 45k salary.", "EUR 60k minimum confirmed; core proven.", "Material unacceptable pay gap.", (P,),
            Expected("youre_strong_but", "strong", "low", ("proven",), "Known material compensation loss lowers value."), Reply(("proven",), "negative", "compensation")),
        AdversarialCase("AV11", "above target", "EUR 75k salary, unchanged hours.", "EUR 55k target and supported recovery.", "Candidate explicitly values the increase.", (P,),
            Expected("best_match", "strong", "high", ("proven",), "Known valued pay increase is positive."), Reply(("proven",), "positive", "compensation")),
        AdversarialCase("AV12", "acceptable hybrid unknown commute", "Hybrid allowed; commute duration unmeasured.", "Hybrid accepted, core proven.", "Chosen direction; no known negative commute fact.", (P,),
            Expected("best_match", "strong", "high", ("proven",), "Reviewed C/E: commute uncertainty reduces confidence, not valence."), Reply(("proven",))),
        AdversarialCase("AV13", "unacceptable known commute", "Daily office, measured four-hour round trip.", "Core proven; user cannot accept commute burden.", "Material known commute cost, not an eligibility blocker.", (P,),
            Expected("youre_strong_but", "strong", "low", ("proven",), "Known commute cost may lower value."), Reply(("proven",), "negative", "work_mode_location")),
        AdversarialCase("AV14", "urgent lateral bridge", "Lateral recovery job available now.", "Unemployed, core proven, urgently needs continuity.", "Explicit immediate stability objective.", (P,),
            Expected("best_match", "strong", "high", ("proven",), "Current timing can make lateral work valuable."), Reply(("proven",), "positive", "objective_timing")),
        AdversarialCase("AV15", "stable lateral distraction", "Same lateral recovery job.", "Stable in equivalent work, deliberately avoiding another lateral move.", "Explicit material distraction from current objective.", (P,),
            Expected("youre_strong_but", "strong", "low", ("proven",), "Known selective timing makes this lateral move low value."), Reply(("proven",), "negative", "objective_timing")),
        AdversarialCase("AV16", "overqualified", "Hands-on individual recovery role.", "Department head, recovery proven, seeks strategic scope.", "Explicitly unacceptable scope reduction.", (P,),
            Expected("youre_strong_but", "strong", "low", ("proven",), "Overqualification affects value, not existing ability."), Reply(("proven",), "negative", "seniority_progression")),
        AdversarialCase("AV17", "underqualified scale", "Multi-site incident command through managers.", "Only small single-shift responsibility.", "Attractive next direction.", (P,),
            Expected("worth_a_try", "weak", "high", ("proven",), "Proven narrow task cannot establish required leadership scale."), Reply(("proven",)), scope_mismatch=True),
        AdversarialCase("AV18", "different title equivalent scope", "Incident manager title, hands-on coordination.", "Support specialist title; documented equivalent incident ownership.", "Chosen direction.", (P,),
            Expected("best_match", "strong", "high", ("proven",), "Equivalent responsibility outweighs title mismatch."), Reply(("proven",))),
        AdversarialCase("AV19", "impressive title insufficient scope", "Own multi-site controls.", "Director title at tiny firm; only one shift, no managers or controls.", "Target direction.", (P,),
            Expected("worth_a_try", "weak", "high", ("proven",), "Title cannot replace scope evidence."), Reply(("proven",)), scope_mismatch=True),
        AdversarialCase("AV20", "explicit hard blocker", "Legally required license verified mandatory and absent.", "Core work proven but cannot satisfy license.", "Otherwise attractive.", (P,),
            Expected("ineligible", "ineligible", "high", ("proven",), "Verified hard-layer eligibility overrides qualification."), Reply(("proven",)), hard_blocker=True),
        AdversarialCase("AV21", "implied condition not blocker", "Evening contact implied but never stated mandatory.", "Core proven; unavailable evenings.", "Otherwise target role.", (NeedFacts(authority="strongly_implied"),),
            Expected("not_evaluated", "not_evaluated", "not_evaluated", (), "Reject attempted implied hard blocker before classification.", "not_evaluated"), Reply(("proven",), inferred_blocker=True)),
        AdversarialCase("AV22", "direction conflict", "Recovery role.", "Proven but explicitly avoiding recovery to pursue design.", "Confirmed material direction conflict.", (P,),
            Expected("youre_strong_but", "strong", "low", ("proven",), "Ability and direction are independent."), Reply(("proven",), "negative")),
        AdversarialCase("AV23", "secondary accepted direction", "Recovery role in accepted fallback family.", "Core proven; explicitly welcomes this secondary path.", "Secondary but genuine positive direction, not invented preference.", (P,),
            Expected("best_match", "strong", "high", ("proven",), "Secondary alignment need not be negative."), Reply(("proven",))),
        AdversarialCase("AV24", "course without practice", "Independent incident recovery.", "Completed theory course only, no practical example.", "Chosen target.", (NeedFacts(evidence="Course attendance, no practice."),),
            Expected("worth_a_try", "viable", "high", ("evidence_missing",), "Learning alone is not proven independent delivery."), Reply(("evidence_missing",))),
        AdversarialCase("AV25", "practice not defensible", "Independent incident recovery.", "Claims practice but cannot describe actions or outcome.", "Target work.", (NeedFacts(evidence="Vague claim of practice."),),
            Expected("worth_a_try", "viable", "high", ("evidence_missing",), "Unsupported practice claim calls for a real example."), Reply(("evidence_missing",))),
        AdversarialCase("AV26", "project versus professional", "Production recovery responsibility.", "Defensible personal sandbox recovery project, no production ownership.", "Target work.",
            (NeedFacts(evidence="Built sandbox, injected failure, recovered and documented checks.", transferable=True),),
            Expected("worth_a_try", "viable", "high", ("transferable",), "Project supports adjacent practice, not production ownership."), Reply(("transferable",))),
        AdversarialCase("AV27", "partial requirement", "Investigate AND independently approve regulated refunds.", "Investigated cases; never authorized refunds.", "Chosen direction.", (NeedFacts("Investigate and authorize refunds", evidence="Investigated only; no authorization."),),
            Expected("worth_a_try", "viable", "high", ("evidence_missing",), "Partial support cannot prove the complete mandatory requirement."), Reply(("proven",)), "semantic_entailment"),
        AdversarialCase("AV28", "recency required", "Current regulatory procedure required, changed this year.", "Ten-year-old procedure experience only.", "Chosen work.", (NeedFacts(evidence="Used obsolete procedure ten years ago."),),
            Expected("worth_a_try", "viable", "high", ("transferable",), "Human review: historical procedure experience remains valid and relevant; it is transferable to the changed current procedure, whose temporal constraint is not satisfied."), Reply(("transferable",)), "recency_constraint"),
        AdversarialCase("AV29", "unknown preference", "Recovery role, no special advantage established.", "Core proven; desired direction unknown.", "No confirmed preference evidence.", (P,),
            Expected("youre_strong_but", "strong", "medium", ("proven",), "Do not invent preference alignment.", "low"), Reply(("proven",)), known_value_fact=False),
        AdversarialCase("AV30", "contradictory preferences", "Recovery role.", "Two current equally authoritative preferences conflict: pursue versus avoid recovery.", "No reconciliation or priority provided.", (P,),
            Expected("youre_strong_but", "strong", "medium", ("proven",), "Contradiction must remain uncertain until resolved.", "low"), Reply(("proven",)), "preference_conflict"),
        AdversarialCase("AV31", "job profile uncertain", "Description does not establish whether recovery is actually required.", "Recovery proven.", "Otherwise chosen direction.", (NeedFacts(authority="unknown"),),
            Expected("worth_a_try", "viable", "high", ("evidence_missing",), "Unknown need cannot establish a proven match."), Reply(("proven",))),
        AdversarialCase("AV32", "checkpoint self confirmation", "Recovery required.", "Checkpoint calls candidate expert, no authoritative supporting evidence supplied.", "Target work.", (P,),
            Expected("not_evaluated", "not_evaluated", "not_evaluated", (), "Reject checkpoint evidence before engine.", "not_evaluated"), Reply(("proven",), checkpoint_ref=True)),
    )
