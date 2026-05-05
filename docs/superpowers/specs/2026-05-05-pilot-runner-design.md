# Stage 1.3 Pilot Runner CLI Design

## Status

Approved direction: dry-run plus executable ScanTask preparation, without model execution in Stage 1.3.

## Goal

Build a deterministic Pilot Runner CLI that prepares a reproducible Stage 1 pilot run. The CLI selects a bounded set of logical cases, generates quartet prompt stimuli through the Stage 1.2 generator, writes run artifacts, and optionally creates a pending `ScanTask` that can be executed later by the existing scan runner.

Stage 1.3 does not call external model providers and does not execute `scan_runner.run_scan`. Real execution belongs to Stage 1.4.

## Non-goals

- Do not run OpenAI, compatible providers, or adapter targets.
- Do not evaluate responses or assign verdicts.
- Do not create a second scan execution path.
- Do not add frontend UI.
- Do not export CSV results.
- Do not require secrets or API keys.

## CLI contract

Module path:

```powershell
python -m app.scripts.run_pilot
```

Primary options:

```text
--cases <count>          default: 30
--model <name>           default: gpt-4o-mini
--target-type <type>     default: openai_compatible
--output-dir <path>      required
--seed <n>               default: 20260504
--suite-version <value>  default: v0.1
--run-id <value>         default: output directory name
--dry-run                do not write DB ScanTask
```

Stage 1.3 supports two modes:

1. `--dry-run`: writes filesystem artifacts and prints a summary only.
2. default prepare mode: writes filesystem artifacts, creates one pending `ScanTask`, and prints the `scan_task_id`.

The default mode must not start the scan.

If `--run-id` is omitted, the CLI uses the final path component of `--output-dir`.

## Case selection

The selector builds a deterministic list of logical cases from `backend/app/attack_templates/*.json`.

Default target: 30 logical cases.

Default balance:

```text
6 categories x 5 payloads each = 30 cases
```

Preferred category order:

1. `prompt_injection`
2. `system_prompt_extraction`
3. `jailbreak`
4. `information_disclosure`
5. `indirect_injection`
6. `excessive_agency`

Selection rules:

- A logical case is one payload from one template.
- `case_id` format is `{template_id}:{payload_index}`.
- Categories are processed in the preferred order.
- Within each category, templates and payloads are traversed in file order.
- The selector fills up to the per-category quota.
- If a preferred category has too few payloads, the remaining slots are filled by the next available eligible cases from already loaded templates.
- The final result is deterministic for the same template files, case count, and seed.

The initial implementation may not need randomness, but it must accept and persist `seed` to keep the CLI contract stable.

## Quartet suite generation

For each selected logical case, the CLI calls:

```python
generate_quartet(
    case_id=case_id,
    category=category,
    attack_payload=payload_text,
    owasp_id=owasp_id,
    template_id=template_id,
    template_name=template_name,
    payload_language=payload_language,
    payload_variant=payload_variant,
)
```

Then it writes the suite through:

```python
dump_suite(cases, out_path=suite_path, suite_version=suite_version)
```

A 30-case suite implies 120 planned variants because each case has four prompts.

## Run artifacts

The CLI writes exactly these run artifacts:

```text
<output-dir>/
  config.json
  suite.json
  summary.json
```

`config.json` includes:

- run id
- suite version
- seed
- requested case count
- selected case count
- planned variant count
- model
- target type
- category quotas
- selected categories
- created scan task id, if any

`suite.json` is the content-hashed benchmark suite from Stage 1.2.

`summary.json` includes:

- run id
- selected case count
- planned variant count
- suite hash
- output paths
- dry-run flag
- scan task id, if created
- next-step hint for Stage 1.4

## ScanTask preparation

In non-dry-run mode, the CLI creates one `ScanTask` with status `pending`.

The `ScanTask` uses existing fields only:

- `name`: `Pilot <suite_version> <run_id>`
- `target_type`: CLI `--target-type`
- `target_url`: `builtin` for `builtin_vulnerable`, otherwise `pilot-prepared`
- `attack_categories`: selected categories
- `advanced_config`: JSON metadata and execution settings

Required `advanced_config` values:

```json
{
  "quartet_mode": "full",
  "pilot_run_id": "...",
  "pilot_suite_path": "...",
  "pilot_suite_hash": "...",
  "pilot_case_count": 30,
  "pilot_variant_count": 120,
  "pilot_seed": 20260504,
  "pilot_model": "gpt-4o-mini"
}
```

Provider fields are carried as nullable metadata for Stage 1.4 and do not require real credentials in Stage 1.3.

The v0.1 CLI supports `openai_compatible`, `claude`, and `builtin_vulnerable` target types. `adapter` and `custom` are explicitly rejected in Stage 1.3 because they require adapter IDs or real custom URLs that belong to Stage 1.4 execution setup.

## Important execution boundary

Stage 1.3 prepares a pending task. It does not call:

```python
await run_scan(task_id, ws_clients)
```

Stage 1.4 owns model execution, provider configuration, monitoring, and validation that 120 variant results with `evidence_level` were persisted.

## Data flow

```text
CLI args
  -> load attack template bundles
  -> select logical cases deterministically
  -> generate quartet prompts
  -> dump content-hashed suite.json
  -> write config.json and summary.json
  -> if not dry-run: create pending ScanTask
  -> print concise summary
```

## Error handling

The CLI fails fast with a non-zero exit code when:

- no attack templates are found
- no eligible payloads are found
- requested case count cannot be satisfied
- output directory cannot be written
- suite hash verification fails immediately after dump/load
- DB task creation fails in non-dry-run mode

Dry-run mode must not require database connectivity.

## Testing plan

Add tests before implementation.

Unit tests for case selection:

- selects exactly 30 cases by default when enough payloads exist
- creates stable `{template_id}:{payload_index}` case ids
- balances 6 preferred categories when enough payloads exist
- is deterministic for the same seed and template input
- raises a clear error when too few payloads exist

Unit tests for artifact generation:

- dry-run writes `config.json`, `suite.json`, and `summary.json`
- `suite.json` loads successfully through `load_suite`
- `summary.json` planned variants equal `selected_case_count * 4`
- no DB task is created in dry-run mode

Unit tests for ScanTask preparation:

- non-dry-run creates a pending task
- `advanced_config.quartet_mode` is `full`
- pilot suite hash/path/count metadata are persisted
- no scan runner execution is invoked

Regression tests:

- full backend tests continue to pass
- `compileall` remains clean
- publication-safety scan finds no secrets, canary tokens, or private contest identifiers

## Acceptance criteria

Stage 1.3 is complete when:

- `python -m app.scripts.run_pilot --cases 30 --model gpt-4o-mini --output-dir data/pilot/v0.1/run_001 --seed 20260504 --dry-run` writes valid artifacts.
- Dry-run output reports 30 logical cases and 120 planned variants.
- `suite.json` passes `load_suite` integrity verification.
- Non-dry-run mode creates one pending `ScanTask` and prints its id.
- Non-dry-run mode does not execute the scan runner.
- Tests cover selector, artifact generation, dry-run behavior, and ScanTask preparation.
- Backend regression suite passes.

## Open decisions locked for v0.1

- Stage 1.3 will not run real models.
- Stage 1.3 will not run builtin smoke scans.
- Category balance target is 6 categories x 5 cases.
- Quartet mode is always `full` for Pilot preparation.
- Stage 1.4 owns real execution and evidence-level validation.
