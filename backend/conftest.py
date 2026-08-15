"""Test-environment settings, mirroring the CI job's env block.

The suite exercises auth-enforced endpoints and localhost/private targets. On a
clean checkout with no .env those settings default to ``auth_required=true`` and
``allow_private_targets=false``, and five integration tests fail. CI supplies the
three values as job env (see .github/workflows/ci.yml), so CI is green while a
plain ``pytest`` is not -- which makes "the suite passes" depend on ambient shell
state rather than on the checkout.

The default sqlite directory is created here for the same reason: it is gitignored
runtime state, so a fresh clone does not have it and sqlite will not create it,
which fails collection of every database-backed test. CI has a dedicated
``mkdir -p data`` step for this.

This file sits at the backend root so it covers both ``app/tests`` and ``tests``:
pytest resolves conftest by directory ancestry, and those two are siblings.

The environment assignment has to happen at import time. ``app.config``
instantiates its ``Settings`` singleton on import, so an autouse fixture would run
too late to affect it. ``setdefault`` leaves an explicitly exported value alone,
so a run that wants auth enforced can still ask for it.
"""

import os
from pathlib import Path

_TEST_ENV = {
    "AUTH_REQUIRED": "false",
    "ALLOW_LOCALHOST_TARGETS": "true",
    "ALLOW_PRIVATE_TARGETS": "true",
}

for _name, _value in _TEST_ENV.items():
    os.environ.setdefault(_name, _value)

(Path(__file__).parent / "data").mkdir(exist_ok=True)
