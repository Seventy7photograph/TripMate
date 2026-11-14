# 文件说明：业务服务：url_safety。
import ipaddress
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


def validate_external_http_url(
    url: str,
    *,
    allowed_hosts: list[str] | None = None,
    allow_private: bool = False,
) -> str:
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("only HTTP and HTTPS URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL credentials are not allowed")
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise UnsafeUrlError("URL hostname is required")

    if allowed_hosts and hostname not in {
        item.strip().lower().rstrip(".") for item in allowed_hosts
    }:
        raise UnsafeUrlError("URL hostname is not in the provider allowlist")

    if hostname == "localhost" or hostname.endswith(".localhost"):
        if not allow_private:
            raise UnsafeUrlError("local provider URLs are disabled")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not allow_private:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise UnsafeUrlError("private or special network addresses are blocked")

    port = parsed.port
    if port is not None and not 1 <= port <= 65_535:
        raise UnsafeUrlError("URL port is invalid")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
