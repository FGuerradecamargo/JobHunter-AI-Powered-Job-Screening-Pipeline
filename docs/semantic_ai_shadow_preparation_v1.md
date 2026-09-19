# Real AI semantic shadow adapter: preparation only v1

## Safety status

Prepared against `a164633` on `feature/postgres-migration`. No live AI request,
credential test, provider ping, billing lookup, Gmail call, external network or
production database access occurred. No production integration, UI/ranking change,
Career Memory mutation, commit or push is included.

All new tests use injected fake transports. The default dry-run was executed with
sockets blocked: eight planned requests, zero executed, feature disabled and model
unconfigured. Fake token counts/request IDs in tests are not real provider usage.

## Infrastructure reused

`services/ai/openai_client.py` already owns OpenAI SDK construction, dotenv/API-key
resolution and a Responses API client. Its existing `generate` method is a plain
text interface used by the Tailored CV adapter. This slice leaves that behavior
unchanged and wraps the same client's `.client.with_options(...)` behind a lazy
transport factory; it does not add a second credential/client stack.

The pinned and installed dependency is `openai==2.46.0`. Local SDK source inspection
confirmed `responses.create`, `text.format` strict JSON Schema, `store`,
`background`, `stream`, `max_output_tokens` and `truncation`. No online documentation
or API was consulted because this slice prohibits all network access. Model-specific
compatibility remains unverified until a later separately authorized shadow run.

The existing source registry, strict dataclass decoder, semantic support validator,
normalization, direct/temporal constraints and request signature are reused.
`models/semantic_evidence.py` and the fixture interpreter remain unchanged.

## Files

All files in this slice are new:

* `models/semantic_ai_shadow.py`: SDK-independent failures, technical metadata and comparisons.
* `services/ai/semantic_shadow_request.py`: minimized projection, opaque IDs, strict schema and parsing.
* `services/ai/openai_semantic_interpreter.py`: double-locked adapter, injected transport, safe diagnostics.
* `scripts/run_semantic_ai_shadow.py`: default dry-run, bounded opt-in CLI.
* `scripts/semantic_shadow_first_batch.json`: frozen first-batch identifiers.
* `tests/test_openai_semantic_shadow.py`: fake-only safety and regression tests.
* `docs/semantic_ai_shadow_preparation_v1.md`: preparation record and future run instructions.

## Architecture and execution locks

The provider-neutral `SemanticSupportInterpreter` interface stays primary.
`OpenAISemanticEvidenceInterpreter.evaluate_semantic_support` returns normalized
domain output or None. Its default runtime authorization is false, including when
called through the protocol. `evaluate` additionally returns the typed shadow
envelope, failure status and usage metadata. No SDK objects leave the transport.

Network execution requires both:

1. `REAL_AI_SEMANTIC_SHADOW_ENABLED=true` in explicitly loaded configuration.
2. `allow_external_ai=True` for that invocation (literal boolean, not a truthy string).

Constructing the adapter alone cannot construct a provider client or send a request.
The constructor defaults to disabled regardless of environment. The standalone
configuration reader uses environment first, then an optional injected Streamlit
secrets mapping. It reads only the feature flag and `SEMANTIC_SHADOW_MODEL`; it
does not read/test credentials. A missing or blank model produces
MODEL_NOT_CONFIGURED before transport construction. There is no model fallback.
The existing CV `OPENAI_MODEL` setting and default are not used or modified.

The CLI reads process environment settings. It does not load dotenv merely to
plan a dry-run; future authorized client construction retains the existing
application's dotenv/API-key convention. No Streamlit secrets were changed.

## Minimized prompt and wire contract

Instruction version: `semantic-support-prompt-v1`.
Adapter version: `openai-semantic-shadow-v1`.

Only supplied selected evidence records and structured job needs are projected.
Evidence includes source-scoped factual text/type, applicable version/date metadata
and relevant opaque capability IDs/transferability flags. Job needs include their
requirement, importance, evidence/temporal requirements and explicit temporal
version boundaries. A full profile is never serialized into the provider payload.

Excluded: candidate/authentication IDs, original source IDs, emails in profile
fields, preferences, objectives, checkpoint prose, whole Career Memory, unrelated
capabilities/experiences, whole CV and whole job-description context. No reference
answers, expected assessments, hiring categories or request signatures are sent.

Selected source text is necessary input, not automatically de-identified prose.
Before a later real-data experiment, the trusted caller must select appropriately
scoped records and review any incidental personal data in that text. The first
batch is synthetic only. This adapter does not claim to solve arbitrary PII removal.

The provider sees opaque `need_N`, `evidence_N` and `capability_N` identifiers.
Responses must use those aliases; guessed original IDs are also rejected. Aliases
are mapped locally, then every relationship passes the existing authority layer.
The adapter requires a relationship for every selected evidence record against
every selected need, preventing silent omission of a supplied contrary source.

Strict schema uses `text.format.type=json_schema`, `strict=true`, required keys on
every object, no additional properties, explicit enums and nullable capability IDs.
It mirrors the semantic link/aggregate contracts. Version, input signature and
source authority are bound locally, not chosen by the model. No free-text rationale,
chain-of-thought, invented facets, question hints or new candidate facts are accepted.
Duplicate JSON keys, malformed types, unknown IDs and extra fields fail closed.

The prompt prohibits invented facts, participation-to-ownership promotion,
lab-to-production promotion, title/skill-label proof, provenance-as-relevance and
obsolete-to-current proficiency assumptions. Uncertainty and conflicts must remain
UNCERTAIN/UNKNOWN. Final assessments and hiring classifications remain downstream.

## Failures, privacy and budgets

Typed failures: DISABLED, NOT_AUTHORIZED, MODEL_NOT_CONFIGURED,
PROVIDER_CLIENT_UNAVAILABLE, REQUEST_BUILD_FAILED, PROVIDER_ERROR, TIMEOUT, REFUSAL,
INCOMPLETE_RESPONSE, INVALID_STRUCTURED_OUTPUT and AUTHORITY_VALIDATION_FAILED.
Every failure abstains; no DIRECT/PROVEN fallback exists.

Future request settings are explicit: `store=false`, `background=false`,
`stream=false`, `truncation=disabled`, 4096 maximum output tokens, 30-second client
timeout and SDK `max_retries=0`. One adapter execution makes at most one Responses
call. No repair, automatic retry, recursive loop or model fallback is implemented.
Any future repair policy needs separate authorization and tests.

Raw provider text is transient and never persisted or included in results/logs.
Only normalized semantic domain data and allowlisted technical metadata are retained.
SDK/HTTP debug loggers on the calling thread are suppressed during transport
construction/execution because the installed SDK can log full request options.
Filters are removed afterward and do not suppress other threads' application work.
Exceptions are converted to fixed codes without their raw strings or stack traces.

Metadata captures operation/schema/prompt/adapter versions, configured model,
input signature, UTC creation time, normalized validation codes, latency, safe
provider request ID and nonnegative provider-reported token counts when available.
There is no monetary estimate or pricing assumption. Model identity is technical
metadata, never evidence authority. Comparison records contain no source prose;
they have frozen `authoritative=false`, expected/observed relation and coverage,
nullable agreement flags, validation status and metadata. A failed run is not a match.

## Frozen first live batch: NOT executed

| ID | Purpose |
| --- | --- |
| SE01 | Obvious DIRECT/FULL |
| SE03 | Obvious ADJACENT/FULL |
| SE05 | NONE/NONE; AV05's irrelevant-source scenario |
| SE10 | PARTIAL compound requirement; AV27's missing approval authority |
| AV06 | Same source evaluated independently for recovery and tax filing |
| SE13 | Project evidence versus professional ownership |
| SE31 | Ambiguous/UNCERTAIN evidence |
| SE02 | Paraphrased direct evidence |

Planned requests: **8**, one per case; AV06 has two needs within one request.
The CLI cannot select arbitrary cases or silently expand to the 54-case benchmark.
Its reference files are hash-checked, and manifest/ID agreement is regression-tested.
The reference judgments are synthetic proposals pending human review, not AI accuracy
targets. Reference answers are used only after generation for comparison.

Safe default command:

```powershell
python scripts/run_semantic_ai_shadow.py
```

It validates and prepares all eight cases, then prints only IDs, model, planned
count and bounded-request metadata. It never instantiates the SDK transport, even
if the feature flag is enabled. Supplying confirmation without `--live` stays dry.

### Future authorized command: DO NOT run in this slice

Prerequisites: human review, a separately approved model explicitly set in process
environment as `SEMANTIC_SHADOW_MODEL`, `REAL_AI_SEMANTIC_SHADOW_ENABLED=true`, and
the existing application's API-key configuration. No model is selected here.

```powershell
python scripts/run_semantic_ai_shadow.py --live --confirm-external-ai --cases SE01 SE03 SE05 SE10 AV06 SE13 SE31 SE02
```

The CLI requires explicit case selection plus both flags and the feature flag. It
prints the plan before any transport use and stops on the first failure. An already
started request may incur cost. No live CLI command was executed in this slice;
authorized-path tests invoke `main` only with injected fake transports.

## Validation results

* New fake-only adapter tests: 52 passed.
* Adapter plus semantic-evidence-v1 focused tests: 140 passed.
* Requested broader domain/authority/security regressions: 796 passed, 2 skipped.
* Full suite: 1582 passed, 2 skipped in 63.27 seconds.
* Full-suite execution guarded socket connection, connect_ex and DNS resolution;
  the existing test fixture isolated SQLite databases and forbade PostgreSQL pools.
* Tracked and new-file whitespace checks passed; only LF/CRLF warnings for new files.
* Git inspection confirmed no edits to existing files, including production pages,
  the shared OpenAI client, Tailored CV factory/adapter and semantic domain contract.
* Seven new files remain uncommitted on `feature/postgres-migration`.

## Remaining uncertainty and next step

The request/parsing/authority boundary is prepared, not certified for real semantic
quality. A structurally coherent false interpretation can still pass; deterministic
validation cannot replace semantic assessment. Model access, model-specific strict
schema compatibility, actual usage, latency and semantic agreement have not been
measured. The smallest justified next step is review of the frozen eight cases and
selection of a model/budget, then a separately authorized shadow-only live experiment.
