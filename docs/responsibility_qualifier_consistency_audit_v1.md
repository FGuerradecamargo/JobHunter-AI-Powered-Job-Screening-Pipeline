# Responsibility qualifier consistency audit v1

Documentation only. Checkpoint: `a164633`; branch: `feature/postgres-migration`.
No existing local work, frozen reference, reply, prompt, schema, engine, or
adapter is changed. Recommendations below are human-review proposals, not
adopted judgments. Batch 001 outputs are not the authority for this audit.

## 1. Audit universe, counting, and principles

Inspected all 40 calibration cases, all 32 adversarial cases, all 54 semantic
references and their controlled replies, both freeze manifests, structured
calibration projections, semantic runner, adversarial runner, and the shadow
batch selection/manifest. Repeated fixtures/projections are not new cases.
Also inspected EvidenceRequirement, TemporalRequirement, semantic normalization,
profile-to-Hiring-Case projection and the engine's separate scope gate.

The corpus has 126 unique suite-qualified cases. **99 contain active explicit
responsibility requirements**, counting the job's explicit role context as
well as the structured need label:

| Suite | Explicit responsibility cases | KEEP / consistent | CHANGE_PROPOSED / inconsistent | NEEDS_DECISION / ambiguous |
| --- | --- | --- | --- | --- |
| semantic-evidence-v1 | 28 | 23 | 4 | 1 |
| adversarial-v1 | 31 | 9 | 20 | 2 |
| calibration | 40 | 38 | 0 | 2 |
| Total | 99 | 70 | 24 | 5 |

Strictly counting current structured need labels, the subset is **63**:
28 SE + 31 AV + 4 HC (HC17a/b and HC18a/b). The remaining 36 HC cases have
explicit ownership/independence in company context, not their need labels.
This distinction prevents inflating the label-only count or missing role context.

AV28 is a special inactive-default case: its authored NeedFacts.text inherits
the independence requirement, but the runner deliberately replaces that label
with the current-procedure requirement. It is audited below as a control, not
counted as an active responsibility case. Counting raw authored fields instead
would yield 100, not 99. Seven additional controls requested for comparison
(SE03, SE18, SE19, SE21, SE35, SE47, AV28) bring the final disposition list to
106 cases: 75 KEEP, 24 CHANGE_PROPOSED, 7 NEEDS_DECISION. The 20 other SE cases
were scanned but contain neither an explicit responsibility qualifier nor one
of these requested control scenarios; they are outside that disposition list.

Searching fixture text was only an audit aid. There is no runtime keyword,
regex, or semantic matching change. Counts are case counts, not need counts;
AV02 has two affected requirements but is counted once.

### Responsibility taxonomy and three situations

- Ownership/accountability: own, personally own, accountable for delivery.
- Independence: independent execution, autonomous handling of the stated task.
- Decision authority: authorize, approve, final decision, signoff.
- Leadership: lead, command, manage through others, accountable operational scope.
- Professional/production responsibility: context alone is not authority, but
  an explicit ownership qualifier is material independently of environment.
- Personal contribution: personally perform/deliver an outcome, not merely a
  collective result or title.

**Type A:** the qualifier is demonstrated by factual actions or another
authoritative case source. Exact keyword repetition is not required.
**Type B:** task practice is demonstrated but the qualifier is not established;
typically DIRECT/PARTIAL or ADJACENT/PARTIAL, never an invented GAP.
**Type C:** the qualifier is explicitly negated or assigned to someone else.
Retain the practiced task. Only the existing source-backed confirmed-absence
rules authorize GAP, not every occurrence of negative wording.

Some cases have no demonstrated task, contradictory sources, or invalid
provenance; these are marked O (other) rather than forced into Type B.
Missing proof of independence does not prove dependent work. A title, the word
"proven" in a narrative, or an expected label is not additional evidence.

Relation measures correspondence of capability. Coverage measures supported
explicit material scope. PARTIAL requires some identifiable task component;
UNKNOWN is appropriate when facts do not establish a defensible partition.
The existing schema couples NONE/NONE and UNCERTAIN/UNKNOWN and allows
DIRECT/ADJACENT only with FULL/PARTIAL. No new pair or facet enum is introduced.

## 2. Reading the matrices

Every row identifies exact need/evidence text directly or by a lossless lookup
in the verbatim catalogs below. Catalog reuse avoids printing the same synthetic
story dozens of times; it is not a paraphrase. Additional-source and constraint
columns explicitly distinguish factual content from supported projection.

Semantic shorthand: D/F = DIRECT/FULL; D/P = DIRECT/PARTIAL;
A/F = ADJACENT/FULL; A/P = ADJACENT/PARTIAL; N/N = NONE/NONE;
U/U = UNCERTAIN/UNKNOWN; R = rejected, not an enum.
State shorthand: P = PROVEN; T = TRANSFERABLE; M = EVIDENCE_MISSING; G = GAP.
For HC/AV, current relation/coverage are **not specified** unless explicitly
noted: their P/T states must not be misreported as a frozen semantic pair.
Proposed pairs in those rows are audit interpretations, not captured outputs.

YES/NO/UNCLEAR concerns proof of the qualifier in available evidence; NO can
mean Type B or C and never automatically means inability. A KEEP may retain
an uncertain or rejected result; it need not mean the qualifier is satisfied.

## 3. Semantic-evidence-v1 responsibility matrix

No additional authoritative source is supplied beyond the listed evidence
unless the row says otherwise. No separate responsibility constraint exists
for these rows; temporal and other non-responsibility controls are covered
later. For multi-source rows, both quoted records are supplied.

| Case | Exact need | Exact evidence | Current pair/state | Qualifier; demonstrated; type | Other sufficient source / separate constraint | Provisional pair/state | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SE04 | Own incident command | Coordinated incident updates under the commander. | A/F/T | own command; NO; B | None / none | A/P/M | CHANGE_PROPOSED |
| SE05 | Own incident recovery | Organized the office lunch rota. | N/N/M | own; NO; O, unrelated task | None / none | N/N/M | KEEP |
| SE10 | Investigate and independently approve refunds | Investigated refunds but never approved them. | D/P/M | independent approval; NO; C | None / no confirmed-gap flag | D/P/M | KEEP |
| SE11 | Investigate and independently approve refunds | Investigated disputed refunds. / Independently approved the resulting refunds. | D/F/P | independent approval; YES; A | Second supplied source completes need / explicit joint support | D/F/P | KEEP |
| SE12 | Investigate approve and audit refunds | Investigated disputed refunds. / Approved refunds; no audit evidence. | D/P/M | approve; YES; A, audit still missing | Second source proves approval, not audit / none | D/P/M | KEEP |
| SE13 | Own professional payroll delivery | Delivered a simulated payroll project. | A/F/T | own professional delivery; NO; B | None / none | A/P/M | CHANGE_PROPOSED |
| SE14 | Independently close monthly accounts | Assisted an accountant with monthly close. | A/F/T | independently; NO; B | None / none; assistance is not an explicit total inability claim | A/P/M | CHANGE_PROPOSED |
| SE16 | Authorize production deployments | Executed deployments authorized by a manager. | A/P/M | authorize; NO; C | None / no confirmed-gap flag | A/P/M | KEEP |
| SE17 | Own a hiring programme | Participated in interview panels. | A/P/M | own programme; NO; B | None / none | A/P/M | KEEP |
| SE22 | Own payroll reconciliation | Office coordinator independently reconciled payroll. | D/F/P | own reconciliation; YES; A | Evidence itself establishes task responsibility / none | D/F/P | KEEP |
| SE23 | Own financial risk decisions | Risk Director title; duties were booking meeting rooms. | N/N/M | own decisions; NO; O | Title is not proof / none | N/N/M | KEEP |
| SE24 | Personally reduce reconciliation errors | Team errors fell; own action unspecified. | U/U/M | personally; UNCLEAR; O | None / none | U/U/M | KEEP |
| SE28 | Approve insurance claims | Scheduled training for insurance sales staff. | N/N/M | approve; NO; O | Shared domain is not approval proof / none | N/N/M | KEEP |
| SE30 | Hold refund approval authority | Explicitly confirmed no refund approval authority. | N/N/G | authority; NO; C | Confirmed absence registered for need / existing GAP rule | N/N/G | KEEP |
| SE31 | Own incident recovery | Helped with incidents; actions unspecified. | U/U/M | own; UNCLEAR; O | None / none | U/U/M | KEEP |
| SE32 | Lead an audit | Audit record ends before role and responsibility are described. | U/U/M | lead; UNCLEAR; O | None / none | U/U/M | KEEP |
| SE33 | Independently approve refunds | I independently approved refunds. / I only assisted; manager held sole approval authority. | U/U/M | independent approval; UNCLEAR; A/C conflict | Both sources conflict; no precedence / conflict normalization | U/U/M | KEEP |
| SE36 | Approve all high-value refunds independently | Approved low-value refunds; high-value required manager approval. | D/P/M | independent high-value approval; NO; C | None / no separate scale flag | D/P/M | KEEP |
| SE39 | Own incident recovery | [] (no evidence records) | U/U/M | own; UNCLEAR; O | None / none | U/U/M | KEEP |
| SE40 | Own audit signoff | Attended audit meeting. / Took notes during audit review. | A/P/M | own signoff; NO; O or B pending materiality | Neither source proves signoff; repetition does not help / none | N/N/M proposed in prior review; A/P/M only if a material audit component is justified | NEEDS_DECISION |
| SE43 | Own budget allocation | Allocated departmental budgets and signed decisions. | D/F/P | own decisions; YES; A | Actions establish accountability without requiring the word own / none | D/F/P | KEEP |
| SE44 | Own budget allocation | Prepared budget options; executive made allocations. | A/F/T | own allocation; NO; C | None / no confirmed-gap flag | A/P/M | CHANGE_PROPOSED |
| SE48 | Personally own escalation decisions | We handled escalations; individual authority unclear. | U/U/M | personally own decisions; UNCLEAR; O | None / none | U/U/M | KEEP |
| SE49 | Investigate and approve refunds | Investigated one refund. / Investigated a second refund; never approved either. | D/P/M | approve; NO; C | Duplicate investigation does not establish approval / none | D/P/M | KEEP |
| SE51 | Own recovery | Evidence belongs to another candidate. | R | own; UNCLEAR; invalid source | Foreign source rejected / ownership isolation | R, no semantic judgment | KEEP |
| SE52 | Own recovery | Derived checkpoint says recovery is proven. | R | own; UNCLEAR; invalid authority | Checkpoint is not evidence / authority rejection | R, no semantic judgment | KEEP |
| SE53 | Own recovery | No such source record. | R | own; UNCLEAR; missing source | None / unknown-ref rejection | R, no semantic judgment | KEEP |
| SE54 | Own recovery | Recovered services. | R | own; NO in text; O, stale request | None / stale-signature rejection takes precedence | R; do not repair stale evidence through semantics | KEEP |

SE51-SE54 must not be reclassified by ignoring their intended security failures.
No accepted authoritative semantic input exists in these rejection probes.

## 4. Adversarial default and exact input catalog

Verbatim shared values:

- **N0**: `Resolve payment incidents independently`
- **E0**: `Traced a failed payment, isolated the cause, restored service and verified settlement.`
- **N2**: `Own releases directly`
- **E2**: `Supported release communications, never owned release.`

`P = NeedFacts()` is a shared object, not all constructors that inherit defaults.
Identity inspection found **22 direct P cases**:
AV01, AV02, AV03, AV06, AV07, AV09, AV10, AV11, AV12, AV13, AV14,
AV15, AV16, AV17, AV18, AV19, AV20, AV22, AV23, AV29, AV30, AV32.

**21 expect P to be PROVEN**: all of these except AV32, whose expected states
are empty because the case must reject checkpoint evidence. AV32's hostile
reply says PROVEN; that is not its expected result.

N0 is inherited by **31 authored cases** (all except AV27); AV28 replaces it
at projection time. E0 is inherited by **25 cases**: the 22 P users plus AV04,
AV21, AV31. No source in E0 explicitly establishes independent execution.

### Additional context is not automatically semantic evidence

AV01's exact candidate context is `Independent recovery with defensible adjacent
coordination in both secondary areas.` This is an explicit independence
assertion in the supplied candidate source projection, and could establish the
qualifier together with E0 if authorized and linked as evidence. However, the
runner registers `context` without usable-evidence status and emits capabilities
from NeedFacts only. The optional semantic request includes those capability
labels as source content, not the candidate context. The current real-shadow
adapter likewise does not send that contextual assertion. This is a source-
selection/representation decision, not permission to ignore an authored fact.

AV18's exact context is `Support specialist title; documented equivalent
incident ownership.` It is potentially relevant, but does not unambiguously
establish independence for N0; it is also not included as semantic evidence.
Most other narratives say only "core proven", which is not new factual proof.
No direct P case has another currently linked usable semantic source proving
independence. Context assertions and referenced evidence are different layers.

For E0 **in isolation**, all 22 P instances have the same D/P interpretation
under the proposed qualifier policy. This does not mean all 22 get a changed
final expected result: AV32 still rejects; AV01/AV18 need source/meaning
decisions; 19 other P cases have a proposed P -> M requirement change.

### Adversarial matrix

All rows are adversarial-v1. Current pairs are unspecified except the explicit
AV05/AV06/AV27 semantic overlays noted below. N0/E0 expand exactly as above.
Unless a row says otherwise: qualifier = independently; demonstration = NO,
Type B; additional sufficient source = none; separate qualifier constraint =
none. The default EvidenceRequirement is DEFENSIBLE, not DIRECT_REQUIRED.

| Case | Exact need / evidence | Current expected state | Demonstration / other authoritative source | Separate constraint | Provisional result | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| AV01 | N0 / E0 | P | NO in E0; context explicitly says Independent recovery, but not linked usable evidence | Important bridges are not proof of core independence | D/P/M on selected evidence; D/F/P possible with authorized context | NEEDS_DECISION |
| AV02 | N0 / E0; N2 / E2 | P; T | NO/B for N0; NO/C for release ownership; no other sufficient source | N2 DIRECT_REQUIRED already reports unmet direct constraint, but does not supply missing ownership | D/P/M; A/P/M | CHANGE_PROPOSED |
| AV03 | N0 / E0 | P (other states G,G) | NO/B; no other sufficient source | Peripheral gaps separate | D/P/M; preserve G,G | CHANGE_PROPOSED |
| AV04 | N0 / E0, source_available=false | M | UNCLEAR usable proof; example unavailable by authoritative ID | Source-repair boundary | M; D/P only after source repaired, not an accepted result now | KEEP |
| AV05 | N0 / Organized lunch rota; no incident recovery. | M; semantic overlay N/N | NO/O; candidate context does not add recovery proof | None | N/N/M | KEEP |
| AV06 | N0 / E0 | P; semantic overlay D/F | NO/B; no other sufficient source | Tax is a separate unrelated need | D/P/M; tax remains N/N/M | CHANGE_PROPOSED |
| AV07 | N0 / E0 | P | NO/B; no other sufficient source | Negative compensation separate | D/P/M | CHANGE_PROPOSED |
| AV08 | N0 / User confirmed cannot perform independent recovery. | G | NO/C, explicit inability; no positive contrary source | confirmed_gap=true | N/N/G | KEEP |
| AV09 | N0 / E0 | P | NO/B; no other sufficient source | Unknown salary does not prove independence | D/P/M | CHANGE_PROPOSED |
| AV10 | N0 / E0 | P | NO/B; no other sufficient source | Below-target pay separate | D/P/M | CHANGE_PROPOSED |
| AV11 | N0 / E0 | P | NO/B; no other sufficient source | Above-target pay separate | D/P/M | CHANGE_PROPOSED |
| AV12 | N0 / E0 | P | NO/B; no other sufficient source | Acceptable commute uncertainty separate | D/P/M | CHANGE_PROPOSED |
| AV13 | N0 / E0 | P | NO/B; no other sufficient source | Known commute cost separate | D/P/M | CHANGE_PROPOSED |
| AV14 | N0 / E0 | P | NO/B; no other sufficient source | Urgent timing separate | D/P/M | CHANGE_PROPOSED |
| AV15 | N0 / E0 | P | NO/B; no other sufficient source | Stable lateral preference separate | D/P/M | CHANGE_PROPOSED |
| AV16 | N0 / E0 | P | NO/B; department-head title is not evidence of this independent task | Down-level preference affects value | D/P/M | CHANGE_PROPOSED |
| AV17 | N0 / E0 | P, global strength WEAK | NO/B for independence; narrow scale explicitly stated | scope_mismatch=true handles scale, not independence | D/P/M for distinct missing qualifier; preserve scale gate | CHANGE_PROPOSED |
| AV18 | N0 / E0 | P | NO in E0; UNCLEAR whether contextual equivalent incident ownership proves independence; not a linked semantic source | Title equivalence not automatic proof | D/P/M on E0; D/F/P requires source adjudication | NEEDS_DECISION |
| AV19 | N0 / E0 | P, global strength WEAK | NO/B for independence; only one shift, no managers or controls | scope_mismatch=true handles scope, not independence | D/P/M for distinct missing qualifier; preserve scope gate | CHANGE_PROPOSED |
| AV20 | N0 / E0 | P, global INELIGIBLE | NO/B; no other sufficient source | Hard eligibility blocker wins globally | D/P/M for requirement; preserve INELIGIBLE | CHANGE_PROPOSED |
| AV21 | N0 / E0 | not_evaluated, no expected states | NO/B in source; need authority strongly_implied | Illegitimate inferred blocker is rejected | Preserve rejection, not a new semantic success | KEEP |
| AV22 | N0 / E0 | P | NO/B; no other sufficient source | Direction preference separate | D/P/M | CHANGE_PROPOSED |
| AV23 | N0 / E0 | P | NO/B; no other sufficient source | Accepted secondary direction separate | D/P/M | CHANGE_PROPOSED |
| AV24 | N0 / Course attendance, no practice. | M | NO/O; theory not execution | None | N/N/M | KEEP |
| AV25 | N0 / Vague claim of practice. | M | UNCLEAR/O; no actions or responsibility supplied | None | U/U/M | KEEP |
| AV26 | N0 / Built sandbox, injected failure, recovered and documented checks. | T | NO/B for independence; context says personal project, no production ownership | transferable=true caps overclaim but does not satisfy independence | A/P/M | CHANGE_PROPOSED |
| AV27 | Investigate and authorize refunds / Investigated only; no authorization. | M; semantic overlay D/P | NO/C for authorize; no other sufficient source | No confirmed-gap flag | D/P/M | KEEP |
| AV29 | N0 / E0 | P | NO/B; no other sufficient source | Unknown preference separate | D/P/M | CHANGE_PROPOSED |
| AV30 | N0 / E0 | P | NO/B; two preference sources add no independence proof | Preference conflict separate | D/P/M | CHANGE_PROPOSED |
| AV31 | N0 / E0 | M | NO/B; need authority unknown, so not an established required qualifier | Unknown need authority prevents proof | Preserve M; do not treat unknown requirement as fact | KEEP |
| AV32 | N0 / E0 is in facts, but reply cites checkpoint:v1 | not_evaluated, no expected states | NO/B in E0; checkpoint is not another sufficient source | Derived-source rejection | Preserve rejection | KEEP |

AV06 also has exact need `File regulated tax returns`, whose original evidence
field is `No tax filing example.` The hostile reply reuses E0. It has no
responsibility qualifier relevant to this audit; neither text supports tax
filing. AV01/AV02 secondary coordination and AV03 optional gaps are not silently
merged into the core qualifier decision.

AV28 control: raw N0 is dormant. Effective need is `Current regulatory procedure
required, changed this year.` Evidence is `Used obsolete procedure ten years
ago.` Current expected T remains KEEP with unsatisfied temporal applicability.
Do not infer a live independence requirement from the unused default.

## 5. Calibration: contextual qualifiers and additional sources

All calibration cases contain explicit role responsibility. The structured
need label and the role context are not interchangeable. `_base` supplies:

**Q**: `Independent mid-level practitioner; supervised escalation for exceptional cases.`

It also supplies the exact company.expected_work string:
`Own day-to-day {need.text.lower()} and explain decisions.`
For each need label in the table this literal substitution gives the exact
context, including its original lower casing; it is not inferred ownership.
HC17a/b replace Q with:
`Manage multiple sites through team leads; accountable for staffing and operational controls.`

Default factual candidate context **C0** is:
`Independently performed the advertised scope.`
This is present in the authored candidate facts, not inferred from a title or
the word PROVEN. Together with concrete compatible task evidence, it suffices
as a synthetic factual assertion of independence for this audit. It cannot
create an example where none exists or override a specific contrary statement.

`structured_calibration_fixtures.py` includes candidate context in the source
projection and preserves it as responsibility_scope; source contexts are also
registered for opportunity interpretation. It projects structured need labels
separately and forwards severe_mismatch as a role-level gate. It does not run
the semantic wire adapter over these cases. Do not claim C0 is automatically
usable per-need source evidence in a future semantic request: that linkage would
need explicit review. This is why stripping all context and downgrading every
HC example would be an invalid audit of the existing whole-case facts.

### Verbatim evidence catalog

| Key | Exact proof.example |
| --- | --- |
| H1 | Reviewed linked payment events, compared device evidence, escalated the pattern and documented the disposition. |
| H1b | No investigation example is stored. |
| H2b | Investigated disputed purchases in customer operations using transaction trails; a defensible bridge, not fraud ownership. |
| H5 | Investigated alerts against account history, recorded escalation reasons and passed a sampled quality review. |
| H6 | Checked beneficial ownership records, resolved documentary inconsistencies and delivered approved review files. |
| H7 | Assembled chronology, separated facts from suspicion, documented the decision and incorporated compliance review feedback. |
| H7b | Claims familiarity but cannot provide any personal decision, action or outcome. |
| H8 | Reconstructed a failed-service timeline, coordinated a correction and confirmed resolution with the customer. |
| H10 | Reproduced a service failure, inspected logs, isolated a configuration fault and verified recovery. |
| H12 | Produced a minimal reproduction, captured logs and validated the release containing the fix. |
| H13 | Identified a failed dependency, used the recovery runbook and verified downstream data completeness. |
| H15 | Interviewed process owners, mapped handoffs, reconciled conflicting needs and obtained sign-off on acceptance criteria. |
| H16 | Observed workflow, modeled decision points, validated exceptions and documented agreed process changes. |
| H17 | Planned shift coverage, reviewed quality exceptions, coached staff and restored service targets. |
| H18 | Allocated work, coached colleagues and coordinated recovery from a missed service target. |
| H19 | Mapped customer objectives, agreed an adoption plan, monitored use and adjusted it after a stakeholder review. |
| H20 | Defined an adoption milestone, coached customer owners and reviewed progress against the agreed plan. |

Additional contexts, exactly:

- C10b: `Only works under close supervision; cannot independently own the advertised incident scope.`
- C17a: `Previously managed comparable multi-site staffing and controls.`
- C17b: `Only led one small shift; no manager-of-managers or multi-site accountability.`
- C18a: `Ready for the first formal team-lead position.`
- C18b: `Already owns several teams and seeks strategic scope; this role is substantial down-leveling.`

### Calibration matrix

All rows: current semantic relation/coverage = not specified. Qualifiers are
role-context own/independent (Q), plus lead for HC17/18 and multi-site
accountability for HC17. Evidence column plus context column form the complete
qualifier-relevant evidence set. YES usually means Type A through an additional
compatible factual source, not that the short example alone says independently.
Expected states show main and extra where present. No separate qualifier
constraint exists unless the row identifies one.

| Case | Exact structured main need (with role context above) | Evidence key | Current states | Demonstrated; other source sufficient | Separate constraint | Provisional result | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HC01a | Investigate fraud patterns | H1 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC01b | Investigate fraud patterns | H1b | M | UNCLEAR/O; C0 asserts scope, but cannot supply absent example | No usable task proof | U/U/M | KEEP |
| HC02a | Investigate fraud patterns | H1 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC02b | Investigate fraud patterns | H2b | T | UNCLEAR; generic C0 versus specifically not fraud ownership | Transferable capability; no global mismatch | A/F/T if only domain bridge; A/P/M or U/U/M if ownership conflict | NEEDS_DECISION |
| HC03a | Investigate fraud patterns | H1 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC03b | Investigate fraud patterns | H1 | P | YES/A; C0; proof wording changes, not story | None | D/F/P | KEEP |
| HC04a | Investigate fraud patterns | H1 | P,G | YES/A for main; C0 | Explicit separate SQL absence | D/F/P; preserve extra G | KEEP |
| HC04b | Investigate fraud patterns | H1 | P,G | YES/A for main; C0 | Same SQL gap becomes core | D/F/P; preserve extra G | KEEP |
| HC05a | Review AML transaction alerts | H5 | P | YES/A; C0 | Compensation separate | D/F/P | KEEP |
| HC05b | Review AML transaction alerts | H5 | P | YES/A; C0 | Compensation separate | D/F/P | KEEP |
| HC06a | Review corporate KYC files | H6 | P | YES/A; C0; approved files do not alone prove approval authority | Timing separate; approval authority not requested | D/F/P | KEEP |
| HC06b | Review corporate KYC files | H6 | P | YES/A; C0 | Timing separate | D/F/P | KEEP |
| HC07a | Document suspicious activity decisions | H7 | P | YES/A; C0; documenting decisions is not claiming sole decision rights | None | D/F/P | KEEP |
| HC07b | Document suspicious activity decisions | H7b | M | UNCLEAR/O; C0 cannot rescue missing concrete actions | No usable task example | U/U/M | KEEP |
| HC08a | Resolve complex escalations | H8 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC08b | Resolve complex escalations | H8 | P | YES/A; C0 | Hard relocation blocker | D/F/P; retain INELIGIBLE | KEEP |
| HC09a | Resolve complex escalations | H8 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC09b | Resolve complex escalations | H8 | P | YES/A; C0 | Work-content preference separate | D/F/P | KEEP |
| HC10a | Diagnose application incidents | H10 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC10b | Diagnose application incidents | H10 | P, global WEAK | NO/C for role independence; C10b | severe_mismatch=true handles role scope, not the unqualified task label | D/F/P for task; separate role gate remains WEAK | KEEP |
| HC11a | Diagnose application incidents | H10 | P,G | YES/A for main; C0 | Explicit SQL querying gap | D/F/P; preserve extra G | KEEP |
| HC11b | Diagnose application incidents | H10 | P,G | YES/A for main; C0 | Same gap despite parser slot | D/F/P; preserve extra G | KEEP |
| HC12a | Reproduce software defects | H12 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC12b | Reproduce software defects | H12, source_available=false | M | YES in factual context C0, but usable task provenance absent | Source repair; not new candidate inability | Preserve M until provenance repaired | KEEP |
| HC13a | Restore failed scheduled jobs | H13 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC13b | Restore failed scheduled jobs | H13 | P | YES/A; C0 | Hard night-shift blocker | D/F/P; retain INELIGIBLE | KEEP |
| HC14a | Restore failed scheduled jobs | H13 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC14b | Restore failed scheduled jobs | H13 | P | YES/A; C0 | Direction preference separate | D/F/P | KEEP |
| HC15a | Map operational requirements | H15 | P,P | YES/A for main; C0 | Extra coordination does not demand independent project ownership | D/F/P; extra D/F/P | KEEP |
| HC15b | Map operational requirements | H15 | P,T | YES/A for main; C0 | Reviewed extra permits defensible transfer, no direct ownership mandate | D/F/P; extra A/F/T | KEEP |
| HC16a | Map operational requirements | H16 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC16b | Map operational requirements | H16 | P | YES/A; C0 | Parser slot does not change scope | D/F/P | KEEP |
| HC17a | Lead operational teams | H17 | P | YES/A; C17a establishes comparable management context | None | D/F/P for leadership and compatible role scope | KEEP |
| HC17b | Lead operational teams | H17 | P, global WEAK | YES for leading a shift; NO/C for broader accountability; C17b | severe_mismatch=true handles multi-site role scope | D/F/P for task; WEAK global | KEEP |
| HC18a | Lead operational teams | H18 | P | UNCLEAR about independent accountability; C18a says ready, not performed independently | No scope gate; first formal role alone is not disproof | D/F/P for task; decide role independence or D/P/M if folded into need | NEEDS_DECISION |
| HC18b | Lead operational teams | H18 | P | YES/A; C18b establishes owning teams, not title alone | Down-level value is separate | D/F/P | KEEP |
| HC19a | Plan customer adoption | H19 | P | YES/A; C0 | Unknown salary separate | D/F/P | KEEP |
| HC19b | Plan customer adoption | H19 | P | YES/A; C0 | Known valued pay separate | D/F/P | KEEP |
| HC20a | Plan customer adoption | H20 | P | YES/A; C0 | None | D/F/P | KEEP |
| HC20b | Plan customer adoption | H20 | P | YES/A; C0 | Acceptable hybrid uncertainty separate | D/F/P | KEEP |

Supplementary exact need/evidence pairs ensure ancillary records are not hidden:

- HC04a/b extra: `Write SQL investigation queries` / `Candidate explicitly cannot write SQL queries independently.`
- HC11a/b extra: `Query production logs with SQL` / `Candidate confirms SQL log querying cannot yet be performed.`
- HC15a extra: `Coordinate cross-functional delivery` / `Tracked dependencies, negotiated scope and secured acceptance across business and engineering.`
- HC15b extra: `Coordinate cross-functional delivery` / `Coordinated support escalations between teams but did not own project delivery.`

These extra need labels do not independently demand ownership. Do not infer
such a mandate from the evidence wording or the generic evidence-collection
question. HC15b's reviewed defensible transfer must not be overturned by turning
"coordinate" into "own". C0 is not used to negate explicit ancillary gaps.

## 6. Six prior change proposals and requested KEEP controls

| Case | Decision | Consistency finding |
| --- | --- | --- |
| SE04 | CHANGE_PROPOSED | A/F/T -> A/P/M: updates under commander do not establish owning command. |
| SE13 | CHANGE_PROPOSED | A/F/T -> A/P/M: simulation supports practice, not explicit professional ownership. |
| SE14 | CHANGE_PROPOSED | A/F/T -> A/P/M: assistance does not establish independently closing accounts. |
| SE19 | NEEDS_DECISION | Prior N/N proposal is about task materiality, not a responsibility qualifier. Browser reset does not explicitly demonstrate backend diagnosis; human review must choose between no component and defensible partial troubleshooting. |
| SE40 | NEEDS_DECISION | Missing signoff is clear; whether attendance/notes support any material audit component remains unresolved. Do not assert N/N purely from qualifier absence. |
| SE44 | CHANGE_PROPOSED | A/F/T -> A/P/M: preparing options does not establish executive allocation authority. |
| SE03 | KEEP | A/F: complete scheduling work in different domain; no explicit ownership qualifier. |
| SE16 | KEEP | A/P: deployment execution is actual underlying operational work; authority explicitly assigned elsewhere. |
| SE17 | KEEP | A/P: interviewing is actual hiring work; owning the programme is not shown. |
| SE18 | NEEDS_DECISION | Provisional A/F can represent scale transfer, but no global scope flag is set in this semantic fixture. Decide whether multinational scope is independently material before changing coverage. |
| SE21 | KEEP | A/F: operated a personal lab cluster; need does not separately require ownership. |
| SE35 | KEEP | A/F historical practice plus separate temporal failure, not an extra ownership penalty. |
| SE36 | KEEP | D/P: approval work established, required high-value independent authority explicitly missing. |
| SE47 | KEEP | A/P: customer service performed, explicitly required Spanish unsupported. Language is functional scope, not an inferred ownership condition. |

Exact control need/evidence records:

- SE03: `Resolve hospital scheduling incidents` / `Resolved retail delivery scheduling incidents.`
- SE18: `Operate a multinational support function` / `Owned support operations for one local office.`
- SE19: `Diagnose backend production failures` / `Helped customers reset browser sessions.`
- SE21: `Operate live Kubernetes clusters` / `Operated a cluster in a personal lab.`
- SE35: `Use the current regulated procedure` / `Executed a superseded procedure.`
- SE47: `Support customers in Spanish` / `Supported customers in Portuguese only.`

The previous impact document remains unchanged as a historical proposal. This
audit narrows SE19/SE40 to NEEDS_DECISION rather than treating the previous
tentative N/N dispositions as approved reference changes.

## 7. Scale integration and project context

AV17 company context: `Multi-site incident command through managers.`
Candidate context: `Only small single-shift responsibility.`
AV19 company context: `Own multi-site controls.`
Candidate context: `Director title at tiny firm; only one shift, no managers or controls.`

Both intentionally set scope_mismatch=True. The runner forwards this as
seniority_context_mismatch; the profile adapter retains it and the engine
forces WEAK (unless already ineligible). Scope is thus an existing independent
Hiring Case gate, not an extra semantic evidence deduction.

Do not force semantic PARTIAL just because this same scale mismatch exists.
For these two cases, the proposed D/P for N0 concerns **independence absent
from E0**, a distinct explicit qualifier, not multi-site scale. The final
strength remains WEAK under either current or proposed requirement state.
If independence were supplied by an authorized source, task support could
remain full while scale still makes the overall case WEAK. HC10b/HC17b likewise
retain task proof and separate explicit role mismatch; their task labels do
not contain N0's independence qualifier.

There is no mismatch identity or automatic deduplication mechanism in the
existing Boolean. A future integration review must identify which fact each
gate handles. Neither removing a genuine gate nor applying it twice is implied.

Project comparison:

- SE21: cluster operation actually practiced; environment differs, no additional
  ownership facet. A/F remains defensible, without claiming production ownership.
- SE13: payroll delivery actually practiced in simulation, but "Own" is explicit
  in the need. Context supports adjacency; missing ownership supports partial.
- AV26: concrete sandbox recovery is practice, not theory. N0 explicitly says
  independently; the source does not. Propose A/P/M, not N/N and not GAP.
  Its narrative says personal project, which alone does not prove autonomy;
  direct ownership of production is also not claimed.

This separation rejects both project-equals-theory and project-implies-ownership.

## 8. Exact blast radius and future options, not executed

### Editing P versus editing defaults

Editing the **P binding** affects exactly 22 adversarial cases, 21 currently
PROVEN expectations, and the aggregate adversarial freeze digest. AV32 must
still reject. P-only edits do not change the separate NeedFacts instances in
AV04/AV21/AV31 even though their evidence strings equal E0.

Editing the **NeedFacts evidence default** affects 25 cases. Editing its
**text default** affects 31 authored cases, 30 effective default labels after
AV28's override. These operations have different blast radii; no such edit was
made. Changing N0 to remove independently would weaken the question rather
than resolve proof. Adding an independence sentence globally would change
source facts, not just repair a label, and could obscure the AV06 lesson.

P underpins unrelated value, timing, salary, commute, eligibility, title, and
scope tests. Changing its semantic assessment globally would stop many from
isolating their intended single adversarial dimension. A later authorized
revision should explicitly choose between (a) better, independently grounded
baseline fixture facts for unrelated controls and (b) relabeling genuinely
incomplete evidence, with new reviewed freezes. Never silently manufacture
candidate facts or update hashes just to pass tests.

### Proposed judgment changes, case counts versus requirement counts

There are **24 CHANGE_PROPOSED cases**: 4 SE and 20 AV. They concern **25
requirement-state changes**, since AV02 has both its recovery P -> M and its
release T -> M. The other AV changes are 18 additional P -> M requirements
and AV26 T -> M. Four SE T -> M changes complete the total. None creates GAP.
Five qualifier cases remain undecided, plus two additional controls.

Conditional downstream effects of applying only these proposed requirement
changes, preserving all other current expected facts/constraints:

| Cases | Expected downstream impact |
| --- | --- |
| AV03, AV11, AV12, AV14, AV23 | STRONG/HIGH/BEST_MATCH -> VIABLE/HIGH/WORTH_A_TRY |
| AV07, AV09, AV10, AV13, AV15, AV16, AV22, AV29, AV30 | STRONG with LOW or MEDIUM value / YOURE_STRONG_BUT -> VIABLE with unchanged value / SKIP_FOR_NOW |
| AV02, AV06, AV26 | Remain VIABLE/HIGH/WORTH_A_TRY; requirement proof changes |
| AV17, AV19 | Remain WEAK/HIGH/WORTH_A_TRY due to separate scope flag |
| AV20 | Remains INELIGIBLE; requirement proof changes |
| SE04, SE13, SE14, SE44 | T -> M; both are non-PROVEN core states, so no automatic strength improvement or deterioration is implied by that distinction alone |

The 14 proposed AV strength/classification changes are policy consequences
deduced from the current engine, not new executed outputs. AV01 and AV18 could
add two more if humans choose evidence-only D/P instead of authorizing context;
they are not included in the 14. Opportunity value is never changed by this
qualifier audit. Existing hostile replies may already disagree with references;
the table compares proposed judgments to frozen expected judgments, not to
every hostile runtime reply.

Relevant later review surfaces: adversarial case facts and expected states,
`hiring_case_review_freeze.json`, controlled replies, semantic reference/reply
and freeze files, semantic AV06 overlay tests, adapter/harness batch manifest
binding, and reports. The 40-case structured SOURCE_SIGNATURES are not affected
by a P-only change; changing HC facts would affect them. Preserve Batch 001 as
a record of its original inputs/results, not a rerendered improved benchmark.

## 9. Final disposition index

These are the only recommendation labels: KEEP, CHANGE_PROPOSED,
NEEDS_DECISION. Each ID appears in exactly one final set. Controls outside the
99 responsibility cases are included and explicitly accounted for above.

### KEEP (75)

- Semantic: SE03, SE05, SE10, SE11, SE12, SE16, SE17, SE21, SE22, SE23, SE24,
  SE28, SE30, SE31, SE32, SE33, SE35, SE36, SE39, SE43, SE47, SE48, SE49,
  SE51, SE52, SE53, SE54.
- Adversarial: AV04, AV05, AV08, AV21, AV24, AV25, AV27, AV28, AV31, AV32.
- Calibration: HC01a, HC01b, HC02a, HC03a, HC03b, HC04a, HC04b, HC05a,
  HC05b, HC06a, HC06b, HC07a, HC07b, HC08a, HC08b, HC09a, HC09b, HC10a,
  HC10b, HC11a, HC11b, HC12a, HC12b, HC13a, HC13b, HC14a, HC14b, HC15a,
  HC15b, HC16a, HC16b, HC17a, HC17b, HC18b, HC19a, HC19b, HC20a, HC20b.

### CHANGE_PROPOSED (24)

- Semantic: SE04, SE13, SE14, SE44.
- Adversarial: AV02, AV03, AV06, AV07, AV09, AV10, AV11, AV12, AV13, AV14,
  AV15, AV16, AV17, AV19, AV20, AV22, AV23, AV26, AV29, AV30.
- Calibration: none.

### NEEDS_DECISION (7)

- Semantic: SE18, SE19, SE40.
- Adversarial: AV01, AV18.
- Calibration: HC02b, HC18a.

The unresolved questions are source inclusion/independence entailment
(AV01/AV18), broad factual scope versus specific evidence (HC02b), independent
role accountability versus informal leadership (HC18a), material global scale
(SE18), and whether any actual task component is supported (SE19/SE40).
They cannot be settled by matching Batch 001's answer.

## 10. Validation boundary

Focused offline semantic, frozen-review, and structured calibration regressions
are appropriate. They verify unchanged behavior and fixture freezes, not that
these proposals have been adopted. Network/DNS connections are blocked during
test execution; test configuration is isolated from production. File hashes
and whitespace checks verify preservation of existing work. Exact results are
reported on completion. No full suite, external call, production access,
commit, push, source-fact edit, or implementation is part of this audit.
