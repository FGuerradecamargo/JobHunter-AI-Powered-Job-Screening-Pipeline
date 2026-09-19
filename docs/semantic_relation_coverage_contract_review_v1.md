# Semantic relation x coverage contract: impact review v1

Status: documentation-only proposal for human review, not an adopted contract.
Branch: `feature/postgres-migration`; safe checkpoint: `a164633`.
All existing uncommitted work is preserved. No prompt, schema, engine, adapter,
fixture, reference, or production behavior changes are made by this review.

## 1. Evidence and method

Reviewed all 54 entries in `tests/semantic_evidence_v1_reference.json` and all
54 controlled replies in `tests/semantic_evidence_v1_replies.json`, along with:

- `models/semantic_evidence.py`
- `services/semantic_evidence_boundary.py`
- `docs/semantic_evidence_applicability_v1.md`
- `docs/semantic_evidence_v1_report.md`
- `docs/real_ai_semantic_shadow_batch_001_review.md`
- `tests/semantic_evidence_v1_runner.py`
- `tests/hiring_case_adversarial_cases.py` and its runner
- `models/hiring_case.py`, `models/profile_interpretation.py`
- `services/hiring_case_engine.py`, `services/profile_hiring_case_adapter.py`
- `services/temporal_applicability.py`

Frozen references are product proposals, not independently human-reviewed gold.
Controlled replies are deliberately aligned contract fixtures, not independent
language-understanding observations. SE51-SE54 intentionally return raw
DIRECT/FULL-shaped replies that are rejected on authority/version grounds;
their expected `rejected` labels are not semantic enum values.

Batch 001 is a reason to inspect ambiguity, not an authority for replacement
labels. This review disagrees with its SE03 and SE13 outputs. Agreement with
its AV06 output is justified by the explicit need, not the model's prestige.
No new AI experiment or counterfactual provider execution was performed.

The matrix below gives one provisional recommended disposition per case, so
counts are reproducible. Human-review flags identify unsettled judgments even
where the provisional label is unchanged. Counts are conditional on adopting
these recommendations; they are not changes already made or score improvements.

## 2. Proposed definitions

### Relation: correspondence of demonstrated capability

Question: **How directly does the demonstrated capability correspond to the
required capability?** It does not count how many components are supported.

- DIRECT: evidence demonstrates substantially the same capability/work. It may
  demonstrate only part of a compound need; DIRECT is not a completeness claim.
- ADJACENT: evidence demonstrates meaningfully transferable capability, with a
  relevant difference in domain, environment, context, scale, or responsibility.
  Shared vocabulary, a title, or membership in the same industry is insufficient.
- NONE: the supplied facts do not materially support the required capability.
  This is a judgment about these records, not the person's total ability.
- UNCERTAIN: available facts are insufficient or conflicting such that the
  relationship cannot safely be determined.

### Coverage: support for explicit material scope

Question: **How much of the requirement's explicit material scope is supported
by the supplied evidence?** It is not a generic similarity score.

- FULL: all explicit material functional components and responsibility
  qualifiers are supported, directly or through defensible adjacent practice.
- PARTIAL: at least one identifiable material component is supported, but at
  least one explicit material component/qualifier is not established.
- NONE: no material component is supported by the supplied record.
- UNKNOWN: the information cannot safely establish completeness or even a
  defensible supported/unsupported partition.

"Unsupported" includes absence of proof, not only explicit inability. Do not
turn it into GAP. Do not require verbatim keywords: equivalent factual actions
can establish responsibility (SE43), while active verbs alone do not always
establish independence (AV06).

Material scope is not every adjective treated as a separate Boolean test.
Domain/context descriptors ordinarily locate practice; authority, independent
execution, named actions, and explicitly required operational capabilities can
be independently material. Reviewers must identify the supported component and
the missing qualifier, rather than inventing a checklist from occupational
knowledge. There are currently no structured facet IDs in the Job Profile.
This proposal introduces neither a facet schema nor a keyword classifier.

### Important existing representation limit

The current boundary `_shape` accepts DIRECT/ADJACENT only with FULL/PARTIAL,
NONE only with NONE, and UNCERTAIN only with UNKNOWN. Conceptual orthogonality
does not mean all 16 enum combinations are currently legal. In particular,
known correspondence with unknown completeness cannot currently be represented
as DIRECT/UNKNOWN or ADJACENT/UNKNOWN. That limitation requires a later human
design decision, not a schema change here. The matrix uses existing legal pairs
and preserves uncertainty where facts do not support a reliable partition.

## 3. Review-only mismatch taxonomy

| Dimension | Normal review consequence; not a new production enum |
| --- | --- |
| TASK / FUNCTION | Same performed work supports DIRECT; distinct but transferable work may be ADJACENT; unrelated work NONE. |
| DOMAIN | Usually relation distance; do not invent missing domain-specific actions. |
| ENVIRONMENT / CONTEXT | Usually relation distance when actual work was practiced. Theory/observation is not execution. |
| SCALE | Relation distance for a transfer bridge; material operational scope or the existing global scope signal requires separate examination. |
| OWNERSHIP | Explicit accountability unsupported despite actual task practice normally means PARTIAL. |
| AUTHORITY | Execution does not prove approval, signoff, or final decision rights. |
| INDEPENDENCE | Explicit independent performance needs factual support, not assumed autonomy. |
| COMPOUND ACTION / FACET | Missing required action means PARTIAL if another is supported. |
| TOOL / METHOD | Actual use in the required task matters; incidental exposure does not establish a component. |
| SENIORITY / RESPONSIBILITY SCOPE | Evaluate demonstrated work, not titles; retain existing independent scope policy. |
| TEMPORAL APPLICABILITY | Existing version/change constraint remains separate; age alone is not deficiency. |
| DIRECT-EVIDENCE CONSTRAINT | Explicit DIRECT_REQUIRED remains separate from semantic transferability. |

These dimensions can coexist. They do not authorize automatic deductions.

## 4. Domain, context, responsibility, and compound rules

### Domain

Same complete functional activity in a different domain normally supports
ADJACENT/FULL. SE03 scheduling, SE29 billing investigation, and SE37 handovers
fit this rule. Nothing in SE03 explicitly specifies a separate hospital-only
action. Hospital familiarity is not silently converted into a missing facet.
If a need separately requires a domain-specific procedure, that component must
be assessed; the rule does not waive it.

### Environment and context

Practiced lab/project work may support ADJACENT/FULL when the whole stated task
was performed. SE21 describes operating a cluster; SE20 describes attending a
theory course; SE15 describes observing execution. They are not equivalent.
SE45 volunteer event logistics can remain DIRECT/FULL because the need does
not demand a professional context: context difference is not automatically
relevant. SE13 differs because it also explicitly demands ownership.

### Ownership, authority, independence

When explicitly required, these are material responsibility qualifiers. A
demonstrated task plus unestablished responsibility normally yields PARTIAL,
with DIRECT or ADJACENT determined independently by the work correspondence.
SE04 coordination under a commander does not establish command ownership;
SE14 assisting does not establish independent close; SE44 preparing options
does not establish making budget allocations. FULL in these references is
inconsistent with the proposed responsibility rule.

The boundary between partial relevant work and no relevant component needs
care. Executing deployments (SE16) or interviewing candidates (SE17) is actual
participation in the underlying operational work. Merely attending an audit
meeting/taking notes (SE40) does not demonstrate audit evaluation or signoff.
This review proposes NONE/NONE for SE40, subject to human adjudication of that
materiality distinction; it does not invent an audit-preparation role.

### Compound requirements

SE10: "Investigate and independently approve refunds" versus "Investigated
refunds but never approved them." remains DIRECT/PARTIAL. Investigation is an
actual supported component; approval is not. SE11 may be DIRECT/FULL when
independent complementary evidence covers approval as well. SE12 still lacks
audit work, and repeated investigation in SE49 does not supply approval.
Existing explicit joint-support validation remains necessary and unchanged.

## 5. Scale and downstream double counting

The current implementation does not have a dedicated semantic scale score or
facet constraint. `HiringCaseInterpretation.seniority_context_mismatch` is
passed by `build_profile_hiring_case_input` to `HiringCaseInput`. In
`determine_hiring_case_strength`, after hard blockers and core GAP checks,
this flag forces WEAK before the remaining semantic evidence-state checks.
It is a separate categorical gate, not an additive numeric penalty.

Adversarial AV17 and AV19 explicitly set `scope_mismatch=True`: narrow task
proof can remain PROVEN while the larger leadership/context requirement makes
strength WEAK. SE18's semantic runner does not set that flag; its request is a
whole-need semantic fixture, not an operational multi-site scope assessment.
Do not claim that SE18 automatically receives a global scope penalty today.

Recommendation for SE18: provisionally retain ADJACENT/FULL for demonstrated
support operations with scale transfer, and require human confirmation of the
scope interpretation. "Multinational" alone does not license inventing
cross-border compliance, management layers, or other missing actions. If the
actual Job Profile expressly requires independently material multi-country
operations, unsupported components may justify PARTIAL. Where the existing
global mismatch flag represents a confirmed role-level scope mismatch, retain
that gate; do not automatically derive it from ADJACENT or PARTIAL.

Before any later integration change, identify whether scale is being handled
as correspondence, a specific missing component, or global role scope. The
current Boolean has no per-mismatch identity for automatic deduplication.
This review cannot promise downstream deduplication that does not exist.
Do not remove genuine scope gates merely to preserve a favorable label.

### Double-penalty principle

One difference must not automatically reduce relation and coverage merely
because both axes can describe it. Different domain alone is not evidence of
incomplete function. Both axes may be reduced when there are distinct facts:
SE13 simulation versus professional context affects correspondence; missing
ownership affects coverage. This is not accidental double counting.

Likewise, execution versus authorization can identify adjacent operational
work and a genuinely unsupported decision component (SE16). The reviewer must
name both the demonstrated work and absent authority, not just say "less
senior" twice. Repeated presentation of one mismatch is not independent proof
of another deficiency. No mechanical deduplication rule is implemented here.

## 6. Current downstream mapping and constraints

| Semantic support | Base state today |
| --- | --- |
| DIRECT/FULL | PROVEN, subject to capability, authority, and temporal safeguards |
| ADJACENT/FULL | TRANSFERABLE |
| DIRECT/PARTIAL or ADJACENT/PARTIAL | EVIDENCE_MISSING |
| NONE/NONE | EVIDENCE_MISSING; GAP only with source-backed confirmed absence |
| UNCERTAIN/UNKNOWN | EVIDENCE_MISSING |

`ResolvedSemanticSupport.support.links` preserves partial relations and
coverage; `supporting_refs` retains DIRECT/ADJACENT source references even for
aggregate EVIDENCE_MISSING. However, `semantic_requirement_links` projects
evidence refs only for PROVEN/TRANSFERABLE; partial states get empty refs and
are not interview-defensible in that legacy projection. Consumers must retain
the full semantic result alongside it. Saying partial evidence is preserved
everywhere downstream would be incorrect.

Other safeguards remain unchanged: unknown confidence/conflicts normalize to
uncertainty; unsupported FULL promotions are capped; transferable capability
metadata cannot be bypassed by omitting its ID; unknown need authority cannot
establish proof. Source-backed absence combined with positive support is a
conflict, not an invitation to select the favorable statement.

`EvidenceRequirement.DEFENSIBLE` can be satisfied by PROVEN or TRANSFERABLE.
`DIRECT_REQUIRED` cannot be satisfied by TRANSFERABLE; the engine makes an
explicit unmet core direct constraint WEAK. Do not convert adjacent evidence
to NONE or PARTIAL solely to implement this separate policy.

`TemporalRequirement.CURRENT_REQUIRED` uses source-backed version/change facts
and temporal evidence; `NOT_REQUIRED` means no age-based penalty. The resolver
returns SATISFIED/NOT_SATISFIED/UNKNOWN/NOT_APPLICABLE. Unestablished current
applicability caps PROVEN at TRANSFERABLE; current NOT_SATISFIED for core or
important needs normally caps strength at VIABLE unless an earlier gate wins.
SE34's age alone does not negate work. SE35 preserves ADJACENT/FULL historical
procedure support with a separate unsatisfied current constraint; SE50 has
current support. Human reviewers should confirm that the changed method, not
age alone, justifies SE35 adjacency. Do not additionally mark coverage PARTIAL
solely for the same currency issue or erase the temporal safeguard.

Aggregate assessment in the impact counts means requirement evidence state,
not hiring strength, quadrant, opportunity value, or employability. Changing
TRANSFERABLE to EVIDENCE_MISSING can leave a core requirement's strength at
VIABLE while changing proof guidance. Opportunity value remains independent.

## 7. All 54 frozen cases: provisional impact matrix

Abbreviations: D = DIRECT, A = ADJACENT, N = NONE, U = UNCERTAIN;
F = FULL, P = PARTIAL, X = NONE, ? = UNKNOWN, R = safe rejection (not an enum).
The scenario column reproduces the frozen scenario names. Current columns are
expected normalized labels, not raw fixture output. "Same" compares both axes.
"Review" means targeted human adjudication required by this impact analysis;
No does not upgrade an agent-authored reference to human gold.

| ID | Scenario | Current relation | Current coverage | Primary dimension | Proposed relation | Proposed coverage | Same | Rationale | Review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SE01 | Exact execution | D | F | Task | D | F | Yes | Explicit independent restoration supports the requested restoration. | No |
| SE02 | Paraphrased execution | D | F | Task | D | F | Yes | Bringing service online demonstrates recovery; no independence qualifier in need. | No |
| SE03 | Adjacent domain | A | F | Domain | A | F | Yes | Retail scheduling resolves the complete functional task; hospital domain is the bridge. | Yes |
| SE04 | Adjacent responsibility | A | F | Ownership | A | P | No | Incident updates are practiced, but work under a commander does not establish owning command. | Yes |
| SE05 | Irrelevant valid source | N | X | Task | N | X | Yes | Lunch rota has no material recovery component. | No |
| SE06 | Generic skill | U | ? | Tool / task uncertainty | U | ? | Yes | SQL label supplies no diagnostic example or reliable completeness partition. | No |
| SE07 | Related reuse recovery | D | F | Task | D | F | Yes | Recovery is explicitly performed, even though the same record also describes communication. | No |
| SE08 | Related reuse communication | D | F | Task | D | F | Yes | Restoration-status communication directly supports this separate need. | No |
| SE09 | Unrelated reuse | N | X | Task | N | X | Yes | Recovery cannot establish tax filing. | No |
| SE10 | Compound partial | D | P | Compound action / authority | D | P | Yes | Investigation performed; approval explicitly not performed. | No |
| SE11 | Complementary sources | D | F | Compound action | D | F | Yes | Investigation plus independent approval can jointly cover the need; count alone is insufficient. | No |
| SE12 | Incomplete combination | D | P | Compound action | D | P | Yes | Investigation and approval do not establish the required audit. | No |
| SE13 | Project vs ownership | A | F | Context + ownership | A | P | No | Simulated payroll practice is relevant; professional ownership is not established. | Yes |
| SE14 | Assistance | A | F | Independence | A | P | No | Assisted close supports related practice, not independent close. | Yes |
| SE15 | Observation | N | X | Task / observation | N | X | Yes | Watching failover does not establish execution. | No |
| SE16 | Execution not authority | A | P | Authority | A | P | Yes | Actual deployment work is adjacent; authorization belonged to the manager. | Yes |
| SE17 | Participation not ownership | A | P | Ownership / compound scope | A | P | Yes | Interviewing is actual hiring work; owning the programme remains unsupported. | Yes |
| SE18 | Scale bridge | A | F | Scale | A | F | Yes | Operations performed at local scale; retain transfer interpretation pending material-scope decision. | Yes |
| SE19 | Frontend troubleshooting | A | P | Task + environment | N | X | No | Browser reset alone demonstrates neither backend diagnosis nor an identified diagnostic component. | Yes |
| SE20 | Training only | N | X | Context / theory | N | X | Yes | Theory attendance does not show cluster operation. | No |
| SE21 | Lab practice | A | F | Environment | A | F | Yes | Cluster operation practiced; live environment is a bridge, absent separately specified production duties. | Yes |
| SE22 | Title mismatch | D | F | Ownership / title | D | F | Yes | Independently reconciled payroll establishes the required task ownership despite title. | No |
| SE23 | Title inflation | N | X | Task / title | N | X | Yes | Room booking is not risk decision work regardless of title. | No |
| SE24 | Outcome no action | U | ? | Personal contribution | U | ? | Yes | Team outcome cannot establish the individual's action. | No |
| SE25 | Action no outcome requirement | D | F | Task | D | F | Yes | Reconciliation performed; no quantified impact was requested. | No |
| SE26 | Incidental tool | N | X | Tool / task | N | X | Yes | Viewing reports does not show SQL pipeline development. | No |
| SE27 | Central tool | D | F | Tool / task | D | F | Yes | SQL transformations and scheduled reporting demonstrate requested pipeline work. | No |
| SE28 | Domain wrong task | N | X | Task | N | X | Yes | Same insurance domain does not turn training scheduling into claims approval. | No |
| SE29 | Transferable task | A | F | Domain | A | F | Yes | End-to-end billing investigation performed in another domain. | No |
| SE30 | Confirmed absence | N | X | Authority / confirmed absence | N | X | Yes | Explicit source-backed absence permits GAP; not merely missing proof. | No |
| SE31 | Ambiguous scope | U | ? | Ownership / unspecified action | U | ? | Yes | Unspecified help cannot establish a reliable task component or ownership. | No |
| SE32 | Incomplete source | U | ? | Responsibility uncertainty | U | ? | Yes | Truncated role record cannot establish audit leadership. | No |
| SE33 | Conflicting sources | U | ? | Authority conflict | U | ? | Yes | Conflicting approval ownership cannot be resolved favorably without precedence. | No |
| SE34 | Old valid practice | D | F | Temporal | D | F | Yes | Bookkeeping execution remains relevant; no current-change constraint. | No |
| SE35 | Old changed practice | A | F | Temporal + method | A | F | Yes | Preserve historical procedure support and separate current-version failure; review method correspondence. | Yes |
| SE36 | Authority scope missing | D | P | Authority / scale of approval | D | P | Yes | Refund approval performed, but explicit high-value independent authority absent. | Yes |
| SE37 | Defensible transfer | A | F | Domain | A | F | Yes | Full handover coordination in a different operational domain. | No |
| SE38 | Optional not core | N | X | Task | N | X | Yes | Presentation templates do not demonstrate forecasting, regardless of optional relevance. | No |
| SE39 | No records | U | ? | Missing information | U | ? | Yes | No evidence is not confirmed inability. | No |
| SE40 | Repeated weak sources | A | P | Authority / task materiality | N | X | No | Attendance and notes establish no audit evaluation or signoff component; repetition adds no proof. | Yes |
| SE41 | Outcome and action | D | F | Task + outcome | D | F | Yes | Triage redesign and stated reduction support the requested result. | No |
| SE42 | Tool named task absent | N | X | Tool / task | N | X | Yes | App use does not demonstrate database backup administration. | No |
| SE43 | Decision accountability | D | F | Ownership / authority | D | F | Yes | Allocating budgets and signing decisions factually establish ownership. | No |
| SE44 | Proposal not decision | A | F | Authority / ownership | A | P | No | Budget option preparation supports related work; executive allocation leaves own-decision scope unsupported. | Yes |
| SE45 | Volunteer equivalent | D | F | Context | D | F | Yes | Event logistics performed; employment context is not a material requirement here. | No |
| SE46 | Translation equivalent | D | F | Task / language | D | F | Yes | Daily Spanish ticket resolution directly supports Spanish customer service. | No |
| SE47 | Related language insufficient | A | P | Tool / method: language | A | P | Yes | Support work performed, but expressly required Spanish execution unsupported; not just an industry difference. | Yes |
| SE48 | Unclear collective pronoun | U | ? | Independence / authority | U | ? | Yes | Collective escalations do not identify personal decision authority or actions. | No |
| SE49 | Joint duplicate not coverage | D | P | Compound action | D | P | Yes | Two investigations still leave approval unsupported. | No |
| SE50 | Direct separate temporal | D | F | Temporal | D | F | Yes | Current procedure execution and matching current metadata support both independent checks. | No |
| SE51 | External candidate ref | R | R | Provenance / isolation | R | R | Yes | Foreign ownership fails before semantic interpretation can authorize use. | No |
| SE52 | Checkpoint reference | R | R | Source authority | R | R | Yes | Derived checkpoint cannot become source evidence. | No |
| SE53 | Unknown source | R | R | Source availability | R | R | Yes | Unknown reference fails closed. | No |
| SE54 | Stale job version | R | R | Version binding | R | R | Yes | Runner injects stale input signature; label does not authorize stale semantic proof. | No |

### Materiality decisions requiring particular care

SE19 and SE40 are broader consistency findings, not reactions to live model
outputs (neither was in Batch 001). The proposed NONE/NONE means these concrete
records establish no material component, not confirmed candidate incapacity.
Their existing ADJACENT/PARTIAL may be using PARTIAL as weak similarity.
Human reviewers may instead identify a defensible material subtask or choose
UNCERTAIN/UNKNOWN if the record cannot be evaluated safely. Until that decision,
both existing references remain frozen. No invented diagnosis or substantive
audit role can justify preserving partial credit.

SE16/SE17 are retained because actual deployment and candidate interviewing are
operational work underlying the broader requirement, unlike notes/attendance.
This supporting-component interpretation is explicitly flagged for human
review so that it does not become an unexamined exception. SE47 separately
requires a usable language; related-language similarity cannot establish
Spanish execution, but performed customer support is a material component.

## 8. Impact totals and human decision list

Under the single provisional matrix above:

- **48/54 unchanged**, including 4 authority rejections (44/50 semantic cases).
- **2 relation changes**: SE19 and SE40, ADJACENT -> NONE.
- **6 coverage changes**: SE04, SE13, SE14, SE44 FULL -> PARTIAL;
  SE19, SE40 PARTIAL -> NONE.
- **4 aggregate requirement assessment changes**: SE04, SE13, SE14, SE44
  TRANSFERABLE -> EVIDENCE_MISSING under the unchanged current mapping.
- SE19/SE40 stay EVIDENCE_MISSING, but would no longer retain supporting refs
  as positively supporting links. Their source records remain intact.
- **6 distinct cases** have proposed axis changes. These sets overlap and must
  not be added together. None of the counts include AV cases.

Targeted human review: **SE03, SE04, SE13, SE14, SE16, SE17, SE18, SE19, SE21,
SE35, SE36, SE40, SE44, SE47** (14 semantic cases).
Additional adversarial decisions: **AV06 recovery, AV26**; check **AV17/AV19**
for global scope integration. AV05/AV27 remain stable controls.

These counts are conditional proposals, not a benchmark improvement. In
particular, no human approval of SE19/SE40 is implied by including their
proposed dispositions in a count. Alternative human resolutions require a
recount and explicit rationale, never silent reference edits.

## 9. Adversarial applicability review

### AV05: provenance is not relevance

Structured need defaults to "Resolve payment incidents independently";
source says "Organized lunch rota; no incident recovery." NONE/NONE and
EVIDENCE_MISSING remain appropriate. The hostile original PROVEN reply is not
made valid by its source ID. No confirmed inability is inferred.

### AV06 recovery: CHANGE_REFERENCE_PROPOSED

Exact need: **Resolve payment incidents independently**.
Exact source: **Traced a failed payment, isolated the cause, restored service
and verified settlement.**

Propose DIRECT/PARTIAL instead of DIRECT/FULL. Recovery actions are supplied;
independent responsibility is not established. The old PROVEN expectation
assumes a material qualifier not grounded by these facts. Under current
mapping the proposed requirement state is EVIDENCE_MISSING, not GAP.
The co-present tax need remains NONE/NONE and EVIDENCE_MISSING; legitimate
recovery evidence must not prove unrelated tax work. With the unchanged
positive value and no blocker, both old and proposed overall cases remain
VIABLE/HIGH/WORTH_A_TRY. This does not imply equivalent proof completeness.

The default `NeedFacts` evidence is reused beyond AV06. Adoption would require
a separately authorized adversarial-wide review, not editing a shared fixture
to improve one case. No adversarial reference or reply changes occur now.

### AV27: preserve compound partial

The structured need is **Investigate and authorize refunds**; evidence is
**Investigated only; no authorization.** The scenario description additionally
mentions independent approval, but that wording is not silently substituted
for the structured need. DIRECT/PARTIAL and EVIDENCE_MISSING remain coherent:
investigation is established, authorization is not.

### Related adversarial scope/context checks

AV26 has actual sandbox recovery practice and a transferable capability, but
uses the default need requiring independent resolution. Its TRANSFERABLE
reference merits human review under the same independence policy; no revised
AV26 label is asserted as an adopted result. AV17/AV19 explicitly exercise the
separate global scope gate. No blanket change to all uses of `NeedFacts` or
to scope handling is justified by this document.

## 10. Special semantic recommendations

### SE03: KEEP_REFERENCE

Need: **Resolve hospital scheduling incidents**.
Evidence: **Resolved retail delivery scheduling incidents.**
Keep ADJACENT/FULL. The complete stated scheduling-resolution task is
demonstrated in another domain. No separately stated hospital-only function
is missing. Clarify the contract, not the reference, rather than adopting
Batch 001's ADJACENT/PARTIAL. This remains a targeted human sign-off item.

### SE13: CHANGE_REFERENCE_PROPOSED

Need: **Own professional payroll delivery**.
Evidence: **Delivered a simulated payroll project.**
Propose ADJACENT/PARTIAL. Actual payroll practice supports an adjacent
capability; simulation is not theory-only or irrelevant work. Explicit
ownership is not established, so FULL overstates responsibility coverage.
Do not adopt Batch 001's NONE/NONE. Context distance and missing ownership
are two distinct considerations, not one mismatch counted twice.

SE21 lab operation has no additional ownership qualifier; SE20 theory and
SE15 observation do not establish execution; SE14 assistance and SE16/SE17
authority/participation illustrate the responsibility boundary. The adapter's
coarse synthetic `professional_experience` source type must not overrule
the explicit simulated content. No detailed payroll subtasks are invented.

AV06's recommendation is stated in section 9. All proposed reference changes
require explicit human approval and a separate implementation authorization.
No model output is the new truth by default.

## 11. Validation and change boundary

Only this document is new. Existing uncommitted adapter/harness files and the
Batch 001 review remain unchanged. Focused offline semantic/adapter/engine
smoke tests verify existing behavior, not adoption of the proposed labels.
Tests use denied socket connections/DNS and isolated test configuration.
Whitespace checks include the new untracked document as well as tracked diffs.
No OpenAI, LLM, provider, network, production, commit, or push operation is
part of this review. No full suite or live benchmark is necessary for a
documentation-only change. Exact smoke results are reported on completion.
