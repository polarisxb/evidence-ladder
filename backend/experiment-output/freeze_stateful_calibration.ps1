$ErrorActionPreference = "Stop"

$worktreeRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$outputRoot = Join-Path $worktreeRoot "backend\experiment-output"
$manifestPath = Join-Path $outputRoot "stateful-calibration-phase-closure.sha256"

$specificPaths = @(
    "backend\experiments\stateful_paid_gate_suite.json",
    "backend\experiments\stateful_paid_gate_models.json",
    "backend\experiment-output\stateful-paid-gate-analysis.json",
    "backend\experiment-output\stateful-paid-gate-analysis.csv",
    "backend\experiment-output\stateful-paid-gate-analysis.md",
    "backend\experiment-output\stateful-paid-gate-rerun-analysis.json",
    "backend\experiment-output\stateful-paid-gate-rerun-analysis.csv",
    "backend\experiment-output\stateful-paid-gate-rerun-analysis.md",
    "backend\experiment-output\stateful-paid-gate-final-report.md",
    "backend\experiment-output\stateful-calibration-phase-closure.md",
    "backend\experiment-output\formal-pilot-superseded-notice.md",
    "backend\experiment-output\formal-pilot-analysis.md",
    "backend\experiment-output\formal-pilot-analysis.json",
    "backend\experiment-output\formal-pilot-analysis.csv",
    "backend\experiment-output\formal-pilot-analysis-before-after.md",
    "backend\experiment-output\stateful-correction-builtin-dry-run-analysis.md",
    "backend\experiment-output\stateful-correction-builtin-dry-run-analysis.json",
    "backend\experiment-output\stateful-correction-builtin-dry-run-analysis.csv",
    "backend\experiment-output\freeze_stateful_calibration.ps1",
    "backend\app\services\experiment_driver.py",
    "backend\app\services\builtin_probe.py",
    "backend\app\services\target_client.py",
    "backend\app\services\retest_executor_real.py",
    "backend\app\services\evidence_arbiter.py",
    "backend\app\services\retest_policy.py",
    "backend\scripts\analyze_formal_pilot.py",
    "backend\scripts\audit_experiment_output.py",
    "backend\scripts\build_stateful_correction_suite.py",
    "backend\scripts\build_stateful_paid_gate.py",
    "backend\app\tests\test_retest_loop\test_experiment_driver.py",
    "backend\app\tests\test_retest_loop\test_real_executor_probe.py",
    "backend\app\tests\test_retest_loop\test_stateful_probe_policy.py",
    "backend\tests\test_analyze_formal_pilot.py",
    "backend\tests\test_audit_hidden_oracle.py",
    "backend\tests\test_build_stateful_correction_suite.py",
    "backend\tests\test_build_stateful_paid_gate.py"
)

$dirtyPaths = git -C $worktreeRoot status --porcelain=v1 -uall |
    ForEach-Object {
        $path = $_.Substring(3)
        if ($path.Contains(" -> ")) {
            $path = ($path -split " -> ", 2)[1]
        }
        $path.Trim('"').Replace("/", "\")
    } |
    Where-Object {
        $_ -notlike "backend\experiment-output\*" -and
        $_ -notmatch '(^|\\)\.env($|\.)' -and
        $_ -notmatch '(^|\\)(credentials|secrets)(\\|$)'
    }

$dirtyFiles = $dirtyPaths |
    ForEach-Object {
        $path = Join-Path $worktreeRoot $_
        if (Test-Path $path -PathType Leaf) {
            Get-Item $path
        }
    }

$historicalNotices = Get-ChildItem $outputRoot -Directory -Filter "formal-pilot-*" |
    ForEach-Object {
        Get-Item (Join-Path $_.FullName "SUPERSEDED_FOR_THESIS_TESTING.md")
    }

$files = @(
    Get-ChildItem (
        Join-Path $outputRoot "stateful-paid-gate-j55-v54-block1"
    ) -File -Recurse
    Get-ChildItem (
        Join-Path $outputRoot "stateful-paid-gate-j55-v54-block2"
    ) -File -Recurse
    Get-Item ($specificPaths | ForEach-Object {
        Join-Path $worktreeRoot $_
    })
    $dirtyFiles
    $historicalNotices
) |
    Where-Object { $_.FullName -ne $manifestPath } |
    Sort-Object FullName -Unique

$prefixLength = $worktreeRoot.Length + 1
$lines = @(
    "# CALIBRATION_NOT_ANALYSIS",
    "# branch feat/mvp-experiment-driver",
    "# base dbff1b1da965a380be990a2c970b48821bcc2d40"
)

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring($prefixLength).Replace("\", "/")
    $hash = (Get-FileHash -Algorithm SHA256 $file.FullName).Hash.ToLower()
    $lines += "$hash  $relativePath"
}

Set-Content -Encoding UTF8 $manifestPath $lines

$verifiedCount = 0
foreach ($line in Get-Content $manifestPath) {
    if ($line.StartsWith("#")) {
        continue
    }
    if ($line -notmatch "^(?<hash>[0-9a-f]{64})  (?<path>.+)$") {
        throw "invalid manifest line: $line"
    }
    $path = Join-Path $worktreeRoot $Matches.path.Replace("/", "\")
    $actualHash = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLower()
    if ($actualHash -ne $Matches.hash) {
        throw "manifest hash mismatch: $($Matches.path)"
    }
    $verifiedCount += 1
}

if ($verifiedCount -ne $files.Count) {
    throw "manifest entry count mismatch"
}

Write-Output "frozen_files=$($files.Count) verified_files=$verifiedCount"
