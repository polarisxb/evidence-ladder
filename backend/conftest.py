"""Test-environment settings, mirroring the CI job's env block.

The suite exercises auth-enforced endpoints and localhost/private targets. On a
clean checkout with no .env those settings default to ``auth_required=true`` and
``allow_private_targets=false``, and five integration tests fail. CI supplies the
three values as job env (see .github/workflows/ci.yml), so CI is green while a
plain ``pytest`` is not -- which makes "the suite passes" depend on ambient shell
state rather than on the checkout.

The database is a fresh sqlite file in a temporary directory, as on a CI runner.
Several tests create scans through the real app; on the default URL every run
left those rows behind in the developer's ``backend/data/app.db``.

The gitignored ``data`` directory is still created: a fresh clone lacks it, and
other runtime paths (e.g. the judge cache) default below it.

This file sits at the backend root so it covers both ``app/tests`` and ``tests``:
pytest resolves conftest by directory ancestry, and those two are siblings.

The environment assignment has to happen at import time. ``app.config``
instantiates its ``Settings`` singleton on import, so an autouse fixture would run
too late to affect it. ``setdefault`` leaves an explicitly exported value alone,
so a run that wants auth enforced can still ask for it.
"""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_TEST_DB_DIR = tempfile.mkdtemp(prefix="evidence-ladder-tests-")
atexit.register(shutil.rmtree, _TEST_DB_DIR, ignore_errors=True)

_TEST_ENV = {
    "AUTH_REQUIRED": "false",
    "ALLOW_LOCALHOST_TARGETS": "true",
    "ALLOW_PRIVATE_TARGETS": "true",
    "DATABASE_URL": f"sqlite+aiosqlite:///{Path(_TEST_DB_DIR, 'app.db').as_posix()}",
}

for _name, _value in _TEST_ENV.items():
    os.environ.setdefault(_name, _value)

(Path(__file__).parent / "data").mkdir(exist_ok=True)
