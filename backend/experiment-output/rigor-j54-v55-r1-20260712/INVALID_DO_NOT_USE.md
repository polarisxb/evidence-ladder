# Invalid run — do not use

This run was resumed in a new Python process after the initial response cache
had been populated. The builtin target's state store is process-local and was
lost, while the cached textual responses remained. Arm B therefore probed an
empty state store and incorrectly overturned true state changes.

The driver now rejects `--resume` for cached suites using the ephemeral builtin
probe state. Use `rigor-j54-v55-r2-20260712` instead.
