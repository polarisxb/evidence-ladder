---
name: systematic-debugging
description: >-
  Four-phase debugging framework: root cause investigation before fixes.
  Use when encountering any bug, test failure, or unexpected behavior.
  Never jump to solutions without understanding the problem first.
---

# Systematic Debugging

## Core Principle

**ALWAYS find root cause before attempting fixes. Symptom fixes are failure.**

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

## The Four Phases

### Phase 1: Root Cause Investigation

1. **Read Error Messages Carefully** - Don't skip stack traces, note line numbers and error codes
2. **Reproduce Consistently** - Can you trigger it reliably? What are exact steps?
3. **Check Recent Changes** - Git diff, new dependencies, config changes
4. **Trace Data Flow** - Where does the bad value originate? Keep tracing up until source

### Phase 2: Pattern Analysis

1. **Find Working Examples** - Locate similar working code in same codebase
2. **Compare Against References** - Read reference implementation COMPLETELY
3. **Identify Differences** - List every difference, however small
4. **Understand Dependencies** - What settings, config, environment does this need?

### Phase 3: Hypothesis and Testing

1. **Form Single Hypothesis** - "I think X is the root cause because Y"
2. **Test Minimally** - SMALLEST possible change, one variable at a time
3. **Verify Before Continuing** - Didn't work? Form NEW hypothesis, don't stack fixes
4. **If 3+ Fixes Failed** - STOP, question the architecture

### Phase 4: Implementation

1. **Create Failing Test** - Simplest possible reproduction
2. **Implement Single Fix** - ONE change, no "while I'm here" improvements
3. **Verify Fix** - Tests pass? No other tests broken? Issue resolved?

## Red Flags - STOP and Follow Process

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- Proposing solutions before tracing data flow
- "One more fix attempt" when already tried 2+

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| 1. Root Cause | Read errors, reproduce, check changes | Understand WHAT and WHY |
| 2. Pattern | Find working examples, compare | Identify differences |
| 3. Hypothesis | Form theory, test minimally | Confirmed or new hypothesis |
| 4. Implementation | Create test, fix, verify | Bug resolved, tests pass |
