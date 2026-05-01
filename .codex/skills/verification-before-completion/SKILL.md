---
name: verification-before-completion
description: >-
  Run verification commands and confirm output before claiming success.
  Use before committing, creating PRs, or claiming any task is complete.
  Evidence before claims, always.
---

# Verification Before Completion

## Core Principle

**Evidence before claims, always.**

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

## The Gate Function

```
BEFORE claiming any status:
1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
5. ONLY THEN: Make the claim
```

## Verification Requirements

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Build succeeds | Build command: exit 0 | Linter passing |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Feature complete | Line-by-line checklist verified | "Tests pass" |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification
- About to commit without verification
- Relying on partial verification
- Thinking "just this once"

## Key Pattern

```
[Run command] -> [See output] -> [Confirm result] -> "Done"
[No command output] -> "Should work now" / "Looks correct" / "I'm confident"
```
