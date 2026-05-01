---
name: defense-in-depth
description: >-
  Validate at every layer data passes through to make bugs impossible.
  Use when fixing bugs caused by invalid data, or when designing validation
  for API inputs, service boundaries, and security-critical paths.
  Source: obra/superpowers-skills
---

# Defense-in-Depth Validation

## Core Principle

**Validate at EVERY layer data passes through. Make bugs structurally impossible.**

Single validation: "We fixed the bug"
Multiple layers: "We made the bug impossible"

## The Four Layers

### Layer 1: Entry Point Validation
Reject obviously invalid input at API boundary.

```python
@router.post("/scans")
async def create_scan(config: ScanConfig):
    if not config.target_url.strip():
        raise AppException(400, "target_url cannot be empty")
    # ...
```

### Layer 2: Business Logic Validation
Ensure data makes sense for this specific operation.

```python
async def run_attack(target_url: str, template: AttackTemplate):
    if not template.payloads:
        raise AppException(400, "Attack template has no payloads")
    # ...
```

### Layer 3: Environment Guards
Prevent dangerous operations in specific contexts.

```python
async def call_target_api(url: str, payload: str):
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1"):
        if not settings.allow_localhost_targets:
            raise AppException(400, "Localhost targets not allowed in production")
    # ...
```

### Layer 4: Debug Instrumentation
Capture context for forensics when other layers fail.

```python
logger.debug("Sending attack", extra={
    "target": target_url,
    "template_id": template.id,
    "payload_length": len(payload),
})
```

## Applying the Pattern

When you find a bug:
1. **Trace data flow** - Where does bad value originate? Where is it used?
2. **Map all checkpoints** - List every point data passes through
3. **Add validation at each layer** - Entry, business, environment, debug
4. **Test each layer** - Try to bypass layer 1, verify layer 2 catches it
