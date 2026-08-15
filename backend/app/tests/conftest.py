"""Test fixtures for the ``app/tests`` suite.

``backend/tests/`` has its own ``conftest.py``, but pytest resolves conftest
files by directory ancestry and ``app/tests/`` is a sibling, not a descendant --
so nothing in this directory was covered by it.

Origin: the DNS stub below was written independently on the local branch
``feat/judge-cache-latency-hardening`` (commit ``d87d744``) and is adopted here
because the adapter SSRF guard added in this change needs it.
"""
from __future__ import annotations

import ipaddress

import pytest

# A stable, unambiguously public address used by the DNS stub below.
_PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def _deterministic_dns(monkeypatch: pytest.MonkeyPatch):
    """Make the SSRF guard's hostname resolution hermetic.

    ``url_guard`` resolves a hostname before applying its policy, so real
    resolution makes these tests depend on the developer's network and on
    hostnames that are not resolvable anywhere outside their deployment. The
    concrete case: ``app/fixtures/mailbot_agent_adapter.json`` uses the Docker
    Compose service name ``http://mailbot:8003``. Inside Compose that resolves
    to a private address and is admitted because ``docker-compose.yml`` sets
    ``ALLOW_PRIVATE_TARGETS=true``; on a test runner it does not resolve at all,
    and the guard correctly fails closed -- which would turn the mailbot and
    shopbot evidence-wiring tests red for a reason that has nothing to do with
    what they assert.

    Resolve every *hostname* to one fixed public IP so the guard's policy is
    still exercised, deterministically and without touching the network.
    Literal-IP targets never reach ``_resolve_host``, so SSRF tests that use
    literal loopback, RFC1918 or link-local addresses (169.254.169.254 and
    friends) are unaffected and still assert real blocking behaviour.
    """
    import app.services.url_guard as url_guard

    def _fake_resolve(host: str):
        return [ipaddress.ip_address(_PUBLIC_IP)]

    monkeypatch.setattr(url_guard, "_resolve_host", _fake_resolve)
