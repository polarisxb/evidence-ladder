# Stage 1.4 Pilot Execution Design

## Status

Approved direction: execute Stage 1.3 pilot suites through the existing `scan_runner` by adding a bounded pilot suite mode. Automated verification uses builtin or mocked targets; real OpenAI-compatible execution remains a manual acceptance path.

## Goal

Run the pending `ScanTask` prepared by Stage 1.3, execute the exact quartet prompts in the prepared `suite.json`, persist the results through the existing case persistence pipeline, and complete the scan with reproducible counters and artifacts.

Stage 1.4 turns a prepared pilot run into the first executable pilot dataset. It does not export CSV; CSV export remains Stage 1.5.

## Non-goals

- Do not create a second independent scan execution path.
- Do not expand the pilot beyond the cases listed in `suite.json`.
- Do not regenerate quartet prompts at execution time.
- Do not add multi-model batch execution.
- Do not optimize batch performance.
- Do not add retry, resume, or recovery semantics beyond existing scan runner behavior.
- Do not add frontend UI.
- Do not export CSV results.
- Do not add a persisted `evidence_level` database column in Stage 1.4.

## Scope decisions

### Acceptance track

Stage 1.4 uses dual-track acceptance:

1. Automated tests run with `builtin_vulnerable` or mocked target calls, so they are deterministic and do not require secrets.
2. Manual pilot execution supports OpenAI-compatible providers, including the planned `gpt-4o-mini` path, when API credentials are configured by the operator.

### Execution path

Pilot execution must reuse `backend/app/services/scan_runner.py`. The implementation adds a pilot suite branch to the existing runner rather than creating a standalone execution engine.

### Suite as source of truth

The Stage 1.3 `suite.json` is authoritative. Execution uses the exact prompt strings contained in the suite for all four variants:

- `attack`
- `clean`
- `quoted_attack`
- `benign_distractor`

The execution stage must not call `generate_quartet()` or `build_control_variant_prompts()` to regenerate prompts for pilot cases.

### Persistence shape

The expected database shape for the default pilot is:

```text
30 AttackCase rows
30 legacy AttackResult rows
120 AttackCaseVariant rows
```

`ScanTask.total_attacks` and `ScanTask.completed_attacks` count logical cases, not individual variants. For the default pilot, both should end at `30` when execution completes successfully.

### Evidence level

Stage 1.4 does not add an `evidence_level` column. Evidence level remains derived from persisted result data by the existing `autotest_summary` and `evidence_arbiter` path.

## Inputs

Stage 1.4 consumes a `ScanTask` created by Stage 1.3. The task is expected to contain:

```json
{
  "status": "pending",
  "advanced_config": {
    "quartet_mode": "full",
    "pilot_run_id": "run_001",
    "pilot_suite_path": "data/pilot/v0.1/run_001/suite.json",
    "pilot_suite_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "pilot_case_count": 30,
    "pilot_variant_count": 120,
    "pilot_seed": 20260504,
    "pilot_model": "gpt-4o-mini"
  }
}
```

The Stage 1.3 artifact directory contains:

```text
config.json
suite.json
summary.json
```

## Output

A successful pilot execution produces:

- `ScanTask.status == "completed"`
- `ScanTask.total_attacks == suite.manifest.case_count`
- `ScanTask.completed_attacks == suite.manifest.case_count`
- one `AttackCase` per suite case
- one `AttackResult` per suite case for legacy compatibility
- four `AttackCaseVariant` rows per suite case
- `AttackCaseVariant.request_text` exactly equal to the corresponding prompt in `suite.json`
- final `ScanTask.overall_score` computed by the existing scan scoring logic

The existing Stage 1.3 filesystem artifacts remain the source of run configuration. Stage 1.4 does not need to mutate `suite.json` or create CSV output.

## Target configuration

### Builtin path

For automated and no-cost execution, `target_type == "builtin_vulnerable"` uses the existing in-process vulnerable model target.

Expected Stage 1.3 task fields:

```json
{
  "target_type": "builtin_vulnerable",
  "target_url": "builtin",
  "target_config": {"vulnerable_level": 2}
}
```

### OpenAI-compatible path

For real manual pilot execution, `target_type == "openai_compatible"` should use the platform provider path unless the operator explicitly configures a third-party endpoint.

Stage 1.4 should correct the Stage 1.3 executable task contract so that the default OpenAI-compatible task does not use `target_url == "pilot-prepared"`. The existing `target_client.is_platform_openai_target()` treats empty, `default`, or the configured platform base URL as platform targets. Therefore the preferred executable task field is:

```json
{
  "target_type": "openai_compatible",
  "target_url": "default",
  "target_config": {"model": "gpt-4o-mini"}
}
```

This allows `target_client.send_to_target()` to resolve the configured generation provider without forwarding platform keys to arbitrary third-party URLs.

## Runner design

### Pilot mode detection

`run_scan(task_id, ws_clients)` should detect pilot mode after loading the task and `advanced_config`:

```text
pilot_suite_path exists and is non-empty => pilot suite mode
otherwise => existing scan behavior
```

Pilot mode must preserve the existing scan lifecycle:

1. load task
2. set status to `running`
3. set `started_at`
4. apply provider overrides
5. set totals
6. broadcast `scan_started`
7. run health probe and broadcast health snapshot
8. execute cases
9. compute overall score
10. set final status and `completed_at`
11. broadcast final event
12. clean scan stop and health tracker state

### Suite loading and validation

Pilot mode should use `load_suite(Path(pilot_suite_path))`. This validates the suite content hash against the manifest.

Additional validation:

- `advanced_config.pilot_suite_hash`, when present, must match `suite.manifest.content_hash`.
- `advanced_config.pilot_case_count`, when present, should match `suite.manifest.case_count`.
- `advanced_config.pilot_variant_count`, when present, should match `suite.manifest.case_count * 4`.
- Every suite case must include all four variants with non-empty strings.

Validation failure should fail the scan before any case results are persisted.

### Logical case execution

Pilot mode should iterate suite cases directly. For each suite case:

1. build a template-like dict from suite metadata:
   - `id`: `template_id` if present, otherwise `case_id`
   - `name`: `template_name` if present, otherwise `Pilot case {case_id}`
   - `category`: suite case category
   - `category_name`: suite case category
   - `owasp_id`: suite case `owasp_id` or empty string
   - `technique`: `pilot_suite`
2. construct exactly four `case_variant` dicts from suite prompts in stable order
3. execute each variant through the existing target invocation path
4. analyze the completed variants through the existing analysis path
5. persist with `_persist_and_count()`

The stable variant order is:

```text
position 0: attack, primary
position 1: clean
position 2: quoted_attack
position 3: benign_distractor
```

### Case executor support

`backend/app/services/case_executor.py` should expose a focused helper for explicit quartet execution. The helper should reuse existing lower-level primitives rather than duplicating target or analysis logic.

Proposed interface:

```python
async def prepare_explicit_case_attempt(
    task,
    template: dict,
    suite_case,
    *,
    ws_clients: dict | None = None,
) -> dict
```

Responsibilities:

- construct explicit case variants from `suite_case.variants`
- call `execute_case_variant()` for each variant
- call `analyze_case_variants()` once on the completed quartet
- set `case_id` to `suite_case.case_id`
- call `apply_business_verification()` like `prepare_case_attempt()` does

`prepare_case_attempt()` remains unchanged for non-pilot scans.

### Concurrency

Stage 1.4 should prefer deterministic sequential execution for pilot mode.

Rationale:

- The Stage 1 plan explicitly does not optimize pilot batch performance.
- Sequential execution keeps manual API cost and failure triage easier to reason about.
- It avoids introducing new SQLite write contention in the pilot branch.

The existing non-pilot runner behavior may keep its current concurrency.

### Advanced engines and mutations

Pilot suite mode should ignore advanced scan expansion fields:

- `enable_mutations`
- `enable_crescendo`
- `enable_fitd`
- `enable_msj`
- `enable_ice`
- `enable_tap`
- `enable_pair`
- `enable_self_explanation`

If these fields are present on a pilot task, they should not add cases beyond the suite. The suite remains the complete execution plan.

## CLI design

Stage 1.4 should add a small execution script rather than changing Stage 1.3 preparation semantics.

Module path:

```powershell
python -m app.scripts.execute_pilot
```

Primary option:

```text
--scan-task-id <id>    required
```

Behavior:

1. initialize the database with `init_db()`
2. call `run_scan(scan_task_id, {})`
3. reload the task
4. print a concise summary:

```text
scan_task_id=<id>
status=completed
completed_attacks=30
total_attacks=30
vulnerabilities_found=<n>
overall_score=<score>
```

The script does not create artifacts and does not export CSV.

## Error behavior

Stage 1.4 should keep error behavior simple.

### Fail-fast setup errors

The scan should fail before persisting cases when:

- `pilot_suite_path` is missing or unreadable
- suite hash validation fails
- suite metadata does not match `advanced_config`
- a suite case lacks one of the four required prompt variants

### Per-case target or analysis errors

The existing case execution and analysis fallback behavior should apply. A target call that returns an error response can still produce persisted `not_evaluable` result data rather than aborting the whole scan.

Stage 1.4 does not add resume, retry, or recovery semantics.

## Test plan

### `backend/tests/test_pilot_suite_execution.py`

Coverage:

- pilot suite mode executes exact prompts from `suite.json`
- pilot suite mode does not expand `attack_categories` through the template engine
- pilot suite hash mismatch fails before persistence
- pilot suite mode persists one logical case with four variants
- completed counters count cases, not variants

Key assertions for a 2-case fixture:

```text
ScanTask.status == "completed"
ScanTask.total_attacks == 2
ScanTask.completed_attacks == 2
AttackCase count == 2
AttackResult count == 2
AttackCaseVariant count == 8
stored request_text values == suite prompt values
```

### `backend/tests/test_execute_pilot_cli.py`

Coverage:

- CLI requires `--scan-task-id`
- CLI initializes DB and calls `run_scan()`
- CLI prints final status and counters

### Regression coverage

Run the existing scan regression suite to ensure non-pilot scans still use the template-engine path:

```powershell
python -m pytest backend\tests\test_phase1_regression.py backend\tests\test_phase2_adapter_regression.py backend\tests\test_phase3_probe_regression.py
```

## Verification commands

Targeted verification:

```powershell
python -m pytest backend\tests\test_pilot_suite_execution.py backend\tests\test_execute_pilot_cli.py
```

Backend regression:

```powershell
python -m pytest backend\tests\
```

Static syntax check:

```powershell
python -m compileall -q backend\app
```

Manual no-cost pilot smoke:

```powershell
python -m app.scripts.run_pilot --cases 6 --model gpt-4o-mini --target-type builtin_vulnerable --output-dir data\pilot\v0.1\smoke_builtin
python -m app.scripts.execute_pilot --scan-task-id <scan_task_id>
```

Manual real pilot:

```powershell
python -m app.scripts.run_pilot --cases 30 --model gpt-4o-mini --target-type openai_compatible --output-dir data\pilot\v0.1\run_001
python -m app.scripts.execute_pilot --scan-task-id <scan_task_id>
```

The real pilot command assumes the operator has configured the required provider credentials outside the repository.

## Success criteria

Stage 1.4 is complete when:

- A Stage 1.3 prepared `ScanTask` can be executed by `execute_pilot.py`.
- Pilot mode runs only the cases in `suite.json`.
- Stored variant prompts exactly match `suite.json`.
- Builtin or mocked automated tests pass without secrets.
- Manual OpenAI-compatible execution is supported by documented command flow.
- Default pilot execution produces 30 logical case records and 120 variant records.
- `autotest_summary` can derive evidence assessments from the persisted results.
- Existing non-pilot scan runner tests continue to pass.

## Risks and mitigations

### Risk: accidental full template expansion

If pilot mode falls through to `AttackEngine.get_all_templates()`, the scan may run more than the bounded pilot suite.

Mitigation: add tests that set broad `attack_categories` but assert only suite cases are persisted.

### Risk: prompt drift

If execution regenerates control variants, stored prompts may differ from the suite hash.

Mitigation: construct variants only from suite prompt strings and assert exact stored `request_text` values.

### Risk: OpenAI-compatible task points at a fake URL

The Stage 1.3 prepare task currently uses `target_url == "pilot-prepared"` for non-builtin targets. That is not executable for the platform provider path.

Mitigation: update the preparation contract to use `target_url == "default"` for OpenAI-compatible pilot tasks and keep backwards-compatible handling for already prepared tasks where feasible.

### Risk: schema creep

Persisting `evidence_level` directly would broaden the stage into schema and migration work.

Mitigation: keep evidence level derived through existing summary and arbiter services in Stage 1.4.
