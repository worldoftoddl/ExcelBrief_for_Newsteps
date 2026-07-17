"""URL validation that blocks common server-side request forgery targets."""

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    """Raised when a URL is not safe for server-side fetching."""


Resolver = Callable[[str], Iterable[str]]


def _resolve(hostname: str) -> set[str]:
    return {item[4][0] for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)}


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not any(
        (ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved)
    )


def validate_public_url(url: str, resolver: Resolver = _resolve) -> str:
    """Return a normalized HTTP(S) URL after scheme, credentials, port, and DNS checks."""
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise UnsafeUrlError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("Credentials in URLs are not allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError("URL contains an invalid port") from exc
    if port not in {None, 80, 443}:
        raise UnsafeUrlError("Only ports 80 and 443 are allowed")

    try:
        addresses = {str(address) for address in resolver(parsed.hostname)}
    except (OSError, UnicodeError) as exc:
        raise UnsafeUrlError("Hostname could not be resolved") from exc
    if not addresses or not all(_is_public(address) for address in addresses):
        raise UnsafeUrlError("URL resolves to a non-public network address")
    return parsed.geturl()
