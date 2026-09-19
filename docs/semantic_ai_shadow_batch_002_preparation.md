# Semantic AI Shadow Batch 002 Preparation

Implementation alignment only; no live execution is authorized by this document.

- Prompt: `semantic-support-prompt-v2`; wire schema remains unchanged.
- Adapter: `openai-semantic-shadow-v1`; requested model and sanitized returned
  model are captured separately. Provider request ID, token counts, latency and
  prompt/adapter versions remain content-free diagnostics.
- Selection: SE03 SE04 SE13 SE14 SE18 SE19 SE40 SE44 SE55 AV06 AV02 AV26.
- Budget: at most 12 requests, one per case, zero retries, stop on first error.
- Frozen minimal synthetic facts and comparison-only references live in
  `scripts/semantic_shadow_batch_002.json`; its normalized hash is checked by
  `scripts/semantic_shadow_batches.py`. Expected judgments never enter prompts.
- Synthetic narratives use the existing `career_update` evidence source class,
  not a provenance label that implies professional production experience.
  AV02 retains its explicit direct requirement; AV06 has both CORE needs and
  only the recovery source. No semantic normalizer or production caller changed.

## Safety and commands

Dry-run, including input validation, with no SDK client construction:

```powershell
python scripts/run_semantic_ai_shadow.py --batch batch-002
```

Observed plan: 12 planned, 0 executed, model unset, feature disabled,
prompt v2, store=false, max output 4096 tokens/request, zero retries.
No model is silently selected. Configuration is `SEMANTIC_SHADOW_MODEL` and
`REAL_AI_SEMANTIC_SHADOW_ENABLED=true`; key resolution remains with the existing
application client. No key was inspected or validated in this task.

The following WOULD spend credits; it was NOT executed:

```powershell
python scripts/run_semantic_ai_shadow.py --batch batch-002 --live --confirm-external-ai
```

Live mode requires both runtime flags, explicit finite selection, enabled
configuration and a configured model. Either safety lock alone is insufficient.
Dry-run never executes regardless of configuration. No expected cost is guessed;
actual tokens and latency are available only after an authorized execution.
Provider responses use store=false; raw prompts/responses are not logged.

## Batch 001 history

The first-batch manifest, historical review, request/usage metadata and prior
audits remain byte-for-byte unchanged. Original SE references remain archived in
`tests/fixtures/semantic_evidence_v1_original_reference.json`; the original
ambiguous AV06 input is retained by the legacy selector. Original instructions
are archived in `scripts/semantic_shadow_batch_001_prompt.txt`.

The default eight-case selection is NOT a historical replay: the active adapter
now uses prompt v2. Historical reconstruction requires the archived v1 prompt
and original facts; no historical result is overwritten or recomputed here.
Batch 002 explicitly selects corrected AV06 and the reviewed references.

## Files for this slice

Updated: `models/semantic_ai_shadow.py`,
`services/ai/openai_semantic_interpreter.py`,
`services/ai/semantic_shadow_request.py`, `scripts/run_semantic_ai_shadow.py`.
Added: this document, `scripts/semantic_shadow_batch_001_prompt.txt`,
`scripts/semantic_shadow_batch_002.json`, `scripts/semantic_shadow_batches.py`,
`tests/test_semantic_shadow_batch_002.py`.

Before live execution: explicit human approval of model and 12-request budget,
configuration in the execution process, and a fresh successful dry-run.

## Offline validation result

- Final focused voice/UI and semantic adapter tests: 98 passed (fake transports).
- Expanded onboarding/auth/profile/semantic regression: 574 passed.
- Final full suite: 1654 passed, 2 skipped in 58.47 seconds.
- Network connections and DNS were blocked; test database isolation was active.
- Both dry-runs executed zero requests. No external AI/provider calls, production
  access, key validation, commit or push occurred.
- git diff --check and untracked-file whitespace checks passed; LF/CRLF warnings
  only. Historical reports and reviewed fixtures were verified unchanged.
