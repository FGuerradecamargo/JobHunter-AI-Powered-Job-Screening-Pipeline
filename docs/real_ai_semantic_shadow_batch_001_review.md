# Real AI semantic shadow batch 001: human review

Status: review only; no implementation or reference changes authorized here.
Batch: `real-ai-semantic-shadow-batch-001`.

## 1. Preserved completed batch

The completed batch made 8 provider requests and evaluated 9 requirements.
There were zero retries, provider errors, or refusals. Requested/configured
model: `gpt-5.6-sol`; reasoning effort: not configured; `store=false`.
The provider-returned model snapshot was not captured and was not independently
verified. These are historical batch facts, not calls made for this review.

| Case / requirement | Frozen reference | Observed accepted/normalized judgment |
| --- | --- | --- |
| SE01 | DIRECT/FULL | DIRECT/FULL |
| SE03 | ADJACENT/FULL | ADJACENT/PARTIAL |
| SE05 | NONE/NONE | NONE/NONE |
| SE10 | DIRECT/PARTIAL | DIRECT/PARTIAL |
| AV06 recovery | DIRECT/FULL | DIRECT/PARTIAL |
| AV06 tax | NONE/NONE | NONE/NONE |
| SE13 | ADJACENT/FULL | NONE/NONE |
| SE31 | UNCERTAIN/UNKNOWN | UNCERTAIN/UNKNOWN |
| SE02 | DIRECT/FULL | DIRECT/FULL |

Seven case responses were accepted; SE31 was normalized as uncertain support.
The three divergent case responses had no validation issues. Acceptance means
contract-valid, not human-confirmed semantic correctness. All remain shadow,
non-authoritative judgments.

Usage: **5929 input + 971 output = 6900 total tokens**. Agreement was 8/9 for
relation, 6/9 for coverage, and 5/8 cases for both axes. This is agreement with
agent-authored proposals pending human review, not real-world accuracy or gold
label validation. No score improvement is attempted in this review.

### Technical shadow metadata

Request IDs below are technical correlation metadata only, never candidate
evidence. Latencies are recorded request latencies, not total batch wall time.

| Case | Input/output tokens | Latency ms | Request ID |
| --- | --- | --- | --- |
| SE01 | 736/95 | 6093 | req_0ab0073b860b4317b44d3d7411e1bd99 |
| SE03 | 734/99 | 3796 | req_3521a80ac2c342db937b8860bf1867a0 |
| SE05 | 734/95 | 2172 | req_c071330ae49248ff8ec77bc0198f733d |
| SE10 | 738/160 | 5562 | req_0a805cdeab56491bb8822c8bfc9b5ea0 |
| AV06 | 782/233 | 4468 | req_2ed3e27f76a34557918a695b67d81d0d |
| SE13 | 734/95 | 1953 | req_bf1e78d24fb04f2c874c2f838775f365 |
| SE31 | 735/99 | 2859 | req_3dd6f550f7a946548025b83f6e654627 |
| SE02 | 736/95 | 3078 | req_1436821ef6494aa1a756273b77a15223 |

## 2. Exact sanitized review inputs

Method: offline reconstruction through `selected_case` in
`scripts/run_semantic_ai_shadow.py` and `prepare_semantic_request` in
`services/ai/semantic_shadow_request.py`, using the unchanged frozen fixtures.
Networking was blocked. Reconstructed context signatures match the recorded
batch signatures below. These are minimized semantic review records, not saved
raw provider payloads or responses; no credentials, transport envelope, or user
identity is included. No new provider call was needed.

The following shared fields and per-case fields together specify all supplied
semantic input fields. Case IDs and expected answers are review metadata, not
provider input. Local IDs were translated to opaque provider aliases.

### Shared fields, exactly as supplied

For every need:

```json
{
  "importance": "core",
  "evidence_requirement": "defensible",
  "temporal_requirement": "not_required",
  "temporal_constraints": []
}
```

For the single evidence record in each case:

```json
{
  "evidence_ref": "evidence_1",
  "source_type": "professional_experience",
  "capabilities": [
    {"candidate_capability_id": "capability_1", "transferable": false}
  ],
  "temporal_version": "",
  "performed_on": ""
}
```

Local evidence `e0` maps to `evidence_1`; capability `cap` maps to
`capability_1`. No capability label, narrative, seniority, ownership facts,
or additional context was sent. The synthetic `transferable: false` metadata
does not establish direct support for a particular need. No structured facets
field or facet IDs were present. This does not erase qualifiers in need text.

### SE03

- Local need `need` -> provider `need_1`.
- Exact requirement: **Resolve hospital scheduling incidents**
- Exact evidence content: **Resolved retail delivery scheduling incidents.**
- All shared fields above apply; no additional facets/context.
- Expected: **ADJACENT/FULL**; observed: **ADJACENT/PARTIAL**.
- Context signature: `e0389e3a02d1276bfbacd703f41c3f858d6b5fee9e9c098abc5fac1759c98254`.

### AV06: recovery only under review

- Local need `need` -> provider `need_1`.
- Exact requirement: **Resolve payment incidents independently**
- Exact evidence content: **Traced a failed payment, isolated the cause, restored service and verified settlement.**
- All shared fields above apply; no additional facets/context.
- Expected: **DIRECT/FULL**; observed: **DIRECT/PARTIAL**.
- Context signature: `25628ab1a392935d2a02700c9daf51d2c4820a97cd671fcdfb0bfede5bbd3df2`.

The same request also contained local need `tax` -> provider `need_2`, exact
requirement **File regulated tax returns**, with the same shared need metadata
and the same evidence. Its expected and observed result was **NONE/NONE**.
It was not a separate provider request and is not a divergent evaluation.

The shorter phrase in the review brief ("Identified failure, restored payment
and verified settlement") is a paraphrase, not the actual supplied content.
The exact reconstruction above must govern review. Crucially, the need says
**independently**; the evidence does not explicitly establish independent work.

### SE13

- Local need `need` -> provider `need_1`.
- Exact requirement: **Own professional payroll delivery**
- Exact evidence content: **Delivered a simulated payroll project.**
- All shared fields above apply; no additional facets/context.
- Expected: **ADJACENT/FULL**; observed: **NONE/NONE**.
- Context signature: `fa1cf6fcbf990a89afad92d087ab1f8a54afd53d1d7a93832f671a8b3a1130f3`.

The source type actually supplied was `professional_experience`, despite the
content explicitly describing simulation. This coarse fixture metadata/context
tension must not be silently corrected in this review. Provenance cannot turn
simulation into production ownership, nor should its label determine relevance.

## 3. Current contract, unchanged

Sources: `models/semantic_evidence.py`,
`services/ai/semantic_shadow_request.py` (`semantic-support-prompt-v1`), and
`docs/semantic_evidence_applicability_v1.md`.

The enum axes are DIRECT/ADJACENT/NONE/UNCERTAIN and
FULL/PARTIAL/NONE/UNKNOWN. Enum membership alone does not allocate qualifiers.
The current prompt states:

> DIRECT demonstrates the required work/capability itself.
> ADJACENT demonstrates meaningfully transferable work, not the same scope/domain/ownership.
> NONE does not materially support the need. UNCERTAIN means insufficient information.
> FULL covers all material scope; PARTIAL only part; NONE no scope; UNKNOWN cannot be determined.
> Keep relation and coverage separate. Return NONE/NONE or UNCERTAIN/UNKNOWN as appropriate.

It also states:

> Never invent experience, tools, outcomes, dates, scope, seniority or independent ownership.
> Never promote participation to ownership or project/lab work to professional production ownership.
> Never infer current proficiency from obsolete experience, relevance from provenance, or proof
> from a job title or skill label. Do not fill missing facts or favor an optimistic interpretation.

The applicability document maps DIRECT/FULL toward proven support and
ADJACENT/FULL toward transferable support. PARTIAL cannot prove an indivisible
need; source links remain while assessment is evidence missing. NONE is not
automatically a confirmed gap. Temporal applicability and explicit direct
evidence requirements are separate boundaries. These cases are `defensible`,
not `direct_required`.

The existing Job Profile has no structured facets contract: invented facet IDs
are rejected, PARTIAL concerns the whole need, and there is no automatic NLP
facet splitter. Multiple source records do not automatically establish FULL;
joint support requires a semantic judgment.

No recorded explanation identifies why the model selected PARTIAL or NONE.
The prompt expressly excludes reasoning traces/explanations. The hypotheses
below are reviewer analysis, not recovered model reasoning.

## 4. Ambiguity analysis

| Question | Current answer / unresolved boundary |
| --- | --- |
| Domain mismatch | Explicitly relevant to ADJACENT, but "all material scope" could also encompass the domain. No exclusion prevents counting it twice. |
| Context / simulation | Production-ownership promotion is prohibited; transferable practiced work is not explicitly prohibited. Which context constraints reduce coverage is unspecified. |
| Ownership | Named under adjacency and under anti-invention rules; autonomy may also be an independently material requirement. Allocation is not defined. |
| Scale | Could be scope proximity or a missing material capability; no explicit allocation rule. |
| Meaning of PARTIAL | Wording supports partial material scope, not merely some semantic similarity. What constitutes material scope versus contextual distance remains underspecified. |

Therefore **relation/coverage ambiguity exists**. A domain or context difference
can accidentally reduce both axes, but both reductions are not always wrong:
different evidence may also omit a distinct required action or responsibility.
Review must identify that additional unsupported component before calling a
double reduction justified. Lack of structured facet IDs is not proof that
the natural-language requirement has no material qualifiers.

## 5. Neighboring frozen references and controls

The following neighbors are **offline reference proposals, not live results
from this batch**. They are not unquestionable human gold.

| Case | Need | Evidence | Frozen relation/coverage |
| --- | --- | --- | --- |
| SE04 | Own incident command | Coordinated incident updates under the commander. | ADJACENT/FULL |
| SE14 | Independently close monthly accounts | Assisted an accountant with monthly close. | ADJACENT/FULL |
| SE15 | Execute failover | Observed an engineer execute failover. | NONE/NONE |
| SE16 | Authorize production deployments | Executed deployments authorized by a manager. | ADJACENT/PARTIAL |
| SE17 | Own a hiring programme | Participated in interview panels. | ADJACENT/PARTIAL |
| SE18 | Operate a multinational support function | Owned support operations for one local office. | ADJACENT/FULL |
| SE20 | Operate live Kubernetes clusters | Attended a Kubernetes theory course. | NONE/NONE |
| SE21 | Operate live Kubernetes clusters | Operated a cluster in a personal lab. | ADJACENT/FULL |
| SE29 | Investigate healthcare billing anomalies | Investigated telecom billing anomalies end to end. | ADJACENT/FULL |
| SE36 | Approve all high-value refunds independently | Approved low-value refunds; high-value required manager approval. | DIRECT/PARTIAL |
| SE37 | Coordinate aviation shift handovers | Coordinated hospital shift handovers. | ADJACENT/FULL |
| SE44 | Own budget allocation | Prepared budget options; executive made allocations. | ADJACENT/FULL |

SE29/SE37 support SE03's intended transfer interpretation. SE21 supports
distinguishing practiced simulation from SE20 theory or SE15 observation.
SE16/SE17 warn that execution or participation does not prove authority or
complete ownership. SE18 treats scale as a bridge, but SE36 treats restricted
authority as incomplete scope. SE04/SE14/SE44 versus SE16/SE17 expose unresolved
ownership-policy tensions. Do not cherry-pick only neighbors favoring agreement.

### Successful live controls

| Case | Exact need / evidence | What the agreement constrains |
| --- | --- | --- |
| SE01 | Restore failed payment services / Independently restored failed payment services. | DIRECT/FULL for explicit execution. Independence is stated, unlike AV06. |
| SE02 | Recover service after outages / Brought unavailable payment processing back online. | DIRECT/FULL accepts paraphrase; this need does not demand independence. |
| SE05 | Own incident recovery / Organized the office lunch rota. | NONE/NONE handles irrelevant work; simulated payroll is not comparably irrelevant to payroll. |
| SE10 | Investigate and independently approve refunds / Investigated refunds but never approved them. | DIRECT/PARTIAL correctly reflects a missing action, not mere domain distance. |
| SE31 | Own incident recovery / Helped with incidents; actions unspecified. | UNCERTAIN/UNKNOWN fits unspecified actions; AV06 lists concrete recovery steps, while SE13 states practiced delivery without detail. |

These controls constrain possible interpretations, not hidden model causality.

## 6. Recommendations for human resolution

### SE03: CONTRACT_NEEDS_CLARIFICATION

Most plausible discrepancy: coverage-contract ambiguity expressed through the
prompt. Both judgments recognize transferable scheduling work. No separate
hospital-specific action, scale, authority, or regulatory facet is supplied.
Under functional coverage semantics, ADJACENT/FULL is defensible and aligns
with SE29/SE37. Under a literal "all material scope" reading, hospital context
can also motivate PARTIAL. This could be accidental double penalty; it is not
confirmed model error or proven bad reference. Preserve the reference pending
human clarification; KEEP_REFERENCE is the likely outcome if domain alone is
treated as relation distance.

### AV06 recovery: genuinely unresolved; possible reference error

The identifiable potentially unsupported component is **independent execution**,
explicit in the need. The evidence demonstrates tracing, diagnosis, restoration,
and verification; it says nothing explicit about supervision or decision rights.
Thus DIRECT/PARTIAL is reasonable if independence is a material scope constraint.
The reference may have assumed autonomy from active personal verbs. Silence is
not confirmed inability, and no new gap should be invented.

This is not a no-missing-facet case: the text contains the qualifier even though
no structured facet IDs were sent. We cannot prove that this was the model's
reason. Human review must decide whether the evidence suffices for autonomy or
whether explicit support is required. Under the latter policy, CHANGE_REFERENCE
could be justified; under the former, KEEP_REFERENCE and inspect prompt/model
coverage behavior later. No change is made here. The matching tax judgment
shows selective relevance, not proof that recovery coverage is correct.

### SE13: CONTRACT_NEEDS_CLARIFICATION

NONE/NONE is difficult to reconcile with the practiced-lab transfer policy in
SE21. "Delivered" describes practice, unlike attending theory (SE20), watching
(SE15), or only participating (SE17). Avoiding production-ownership inflation
should not automatically erase relevance of practiced payroll delivery.
The model may have over-applied that prohibition, but its reasoning is unknown.

Conversely, FULL is not established simply because the text says "project".
No payroll components or independent ownership details are supplied, and the
need explicitly says "Own professional". SE16/SE17 and the coarse source-type
metadata make this a contract/reference review as well as a possible overly
strict model judgment. Preserve the reference; decide which task components
were actually practiced and which ownership/context constraints are material
before choosing adjacent/full, adjacent/partial, or insufficient information.
Do not replace theory, simulation, execution, and authority with one category.

## 7. Proposed orthogonal semantics: NOT IMPLEMENTED

1. Relation answers: how directly does demonstrated capability correspond to
   required capability?
2. Coverage answers: how much of the requirement's material functional
   facets/components is supported?
3. A different domain or environment may support ADJACENT/FULL. Simulation
   may support ADJACENT/FULL when the whole functional task was practiced;
   this never asserts professional production ownership.
4. A missing action in a compound need produces PARTIAL. Investigation without
   required approval is DIRECT/PARTIAL; irrelevant work is NONE/NONE.
5. Ownership, context, and scale are not automatically relation-only. When
   represented as independent material facets, their absence can reduce
   coverage. Explicit textual qualifiers also require review under the current
   facet-less contract; do not silently ignore "independently" or "Own".
6. Before lowering both axes, identify the distinct unsupported material
   component, not merely repeat the same contextual difference. This is an
   anti-accidental-double-penalty principle, not a ban on valid dual reductions.
7. Distinguish uncertainty from demonstrated absence. Do not infer autonomy,
   full task execution, or lack of ability from missing detail.

This proposal coheres with SE03/SE21/SE29/SE37 and SE10, but is not demonstrably
consistent with every existing ownership/scale reference (notably SE04/SE14/
SE44 versus SE16/SE17/SE36). Human clarification is needed before changing
prompts, introducing facets, recoding judgments, or altering expectations.

## 8. Change boundary and validation

Only this review document is added. Existing uncommitted adapter/harness work
is preserved. No behavior, prompt, schema, validator, deterministic semantic
rule, frozen expectation, or recorded provider reply is changed. No raw
provider payload/response is stored. No production access, external call,
retry, commit, or push is part of this review.

Offline adapter, semantic evidence, and human-review resolution regressions
are the relevant checks; a full application suite is unnecessary for this
documentation-only addition. Network-denied test execution and whitespace
checks are reported in the completion message. Human approval of the axis
policy and per-case resolutions is the next step, not another provider batch.
