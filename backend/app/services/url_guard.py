"""SSRF protection (Stage 1.1b).

Single chokepoint for validating *user-supplied* target URLs before any
outbound HTTP fetch. Every ingress that accepts a URL from the API
client must call :func:`validate_target_url` before using the value.

Policy
------
* **Scheme allow-list**: ``http``, ``https``. Everything else (file://,
  gopher://, dict://, ftp://, ldap://, …) is rejected.
* **Host block-list** (after DNS resolution if the host is a name):

  - loopback (``127.0.0.0/8``, ``::1``) — opt-in via ``allow_localhost``
    so local development can still hit ``mock_targets/`` running on
    127.0.0.1
  - RFC 1918 private (``10/8``, ``172.16/12``, ``192.168/16``)
  - link-local (``169.254/16``, ``fe80::/10``) — *not* relaxed by
    ``allow_localhost`` because this also blocks the AWS/GCP metadata
    service ``169.254.169.254``
  - CGNAT (``100.64/10``)
  - IPv6 unique-local (``fc00::/7``)
  - unspecified (``0.0.0.0`` / ``::``) and other reserved ranges
* **Hostname static block-list**: known cloud metadata service names
  (``metadata.google.internal``, ``metadata``, ``instance-data``).
  These are blocked even if DNS resolution fails in the local
  environment.

DNS rebinding (where a host resolves to a public IP at validation time
and a private IP at fetch time) is *partially* mitigated by checking
all addresses returned by ``getaddrinfo`` and rejecting the URL if any
resolution falls in a blocked range. Full mitigation (pin-then-fetch
on the same IP) is out of scope for Stage 1.1b — see Stage 2 backlog.

Usage
-----
::

    from app.services.url_guard import validate_target_url

    validate_target_url(target_url)                   # production default
    validate_target_url(target_url, allow_localhost=True)  # dev / mock_targets
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.config import settings
from app.core.exceptions import AppException


__all__ = ["UnsafeTargetURL", "validate_target_url"]


_ALLOWED_SCHEMES = frozenset({"http", "https"})

_BLOCKED_HOSTNAMES = frozenset(
    {
        # GCP / Azure / AWS metadata service common host names.
        "metadata.google.internal",
        "metadata",
        "instance-data",
        # Defensive: localhost variants we never want even by string.
        "ip6-localhost",
        "ip6-loopback",
    }
)


class UnsafeTargetURL(AppException):
    """Raised when a target URL fails the SSRF guard.

    Inherits :class:`AppException` so the FastAPI handler returns a
    proper HTTP 400 with the reason in the response body. The handler
    in ``app.core.exceptions`` only reads ``status_code`` and ``detail``
    so we don't expose the raw URL twice.
    """

    def __init__(self, reason: str, url: str) -> None:
        detail = f"Refused unsafe target URL ({reason}): {url}"
        super().__init__(status_code=400, detail=detail)
        self.reason = reason
        self.url = url


def _resolve_host(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve ``host`` to all IPs via ``getaddrinfo``.

    Returns an empty list if resolution fails. Callers must decide
    whether an unresolvable host is allowed (we treat it as blocked
    for safety unless the host string itself is on the blocked-hostname
    list, in which case the rule fires earlier).
    """
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []

    out: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for family, _, _, _, sockaddr in infos:
        if not sockaddr:
            continue
        addr = sockaddr[0]
        try:
            if family == socket.AF_INET:
                out.append(ipaddress.IPv4Address(addr))
            elif family == socket.AF_INET6:
                # Strip IPv6 zone id if present (``fe80::1%eth0``).
                out.append(ipaddress.IPv6Address(addr.split("%", 1)[0]))
        except (ValueError, ipaddress.AddressValueError):
            continue
    return out


def _is_blocked_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_loopback: bool,
    allow_private: bool = False,
) -> tuple[bool, str]:
    """Return ``(is_blocked, reason)`` for a single resolved IP."""
    if ip.is_unspecified:
        return True, "unspecified address"
    if ip.is_loopback:
        if allow_loopback:
            return False, ""
        return True, "loopback address"
    if ip.is_link_local:
        # Covers AWS/GCP metadata 169.254.169.254 and IPv6 fe80::/10.
        # Intentionally NOT relaxed by allow_loopback or allow_private.
        return True, "link-local address"
    if ip.is_multicast:
        return True, "multicast address"
    if ip.is_private:
        if allow_private:
            return False, ""
        # RFC1918, ULA fc00::/7, 100.64/10 (CGNAT) etc.
        return True, "private/reserved address"
    if ip.is_reserved:
        return True, "reserved address"
    return False, ""


def validate_target_url(
    url: str,
    *,
    allow_localhost: bool | None = None,
    allow_private: bool | None = None,
) -> str:
    """Validate ``url`` against the SSRF policy. Returns the URL on success.

    Parameters
    ----------
    url:
        The user-supplied URL to validate. Must be absolute with an
        ``http`` / ``https`` scheme.
    allow_localhost:
        Whether to permit loopback addresses (``127.0.0.0/8``, ``::1``,
        ``localhost``). Defaults to ``settings.allow_localhost_targets``
        when ``None``. RFC1918, link-local, CGNAT etc. are *always*
        blocked regardless of this flag.
    allow_private:
        Whether to permit RFC1918 private addresses (Docker Compose
        internal networking). Defaults to
        ``settings.allow_private_targets`` when ``None``.

    Raises
    ------
    UnsafeTargetURL
        On any policy violation. The exception's ``status_code`` is 400
        and ``detail`` describes the reason.
    """
    if allow_localhost is None:
        allow_localhost = bool(settings.allow_localhost_targets)
    if allow_private is None:
        allow_private = bool(settings.allow_private_targets)

    if not url or not isinstance(url, str):
        raise UnsafeTargetURL("empty or non-string url", url or "")

    parts = urlsplit(url.strip())

    scheme = (parts.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeTargetURL(
            f"scheme '{scheme or '(missing)'}' not in {sorted(_ALLOWED_SCHEMES)}",
            url,
        )

    # ``urlsplit`` keeps the raw host (including IPv6 brackets) in
    # ``netloc``; ``hostname`` is lowercased and bracket-stripped.
    host = (parts.hostname or "").strip()
    if not host:
        raise UnsafeTargetURL("missing host", url)

    # Static hostname block list (covers cloud metadata services even
    # when DNS does not resolve in this environment).
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise UnsafeTargetURL(f"blocked hostname '{host}'", url)

    # If host parses as a literal IP, validate it directly. Otherwise
    # resolve via DNS and validate every returned address (anti
    # rebinding, tier 1).
    try:
        literal = ipaddress.ip_address(host)
        addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [literal]
    except ValueError:
        addresses = _resolve_host(host)
        if not addresses:
            raise UnsafeTargetURL(
                f"hostname '{host}' did not resolve", url
            )

    for ip in addresses:
        blocked, reason = _is_blocked_ip(ip, allow_loopback=allow_localhost, allow_private=allow_private)
        if blocked:
            raise UnsafeTargetURL(f"{reason} ({ip})", url)

    return url
