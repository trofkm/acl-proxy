import ipaddress
import re
from typing import List, Tuple

from fastapi import HTTPException

_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")
_PORT_RE = re.compile(r":(\d{1,5})$")
_TOKEN_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")

_MAX_HOSTS_LENGTH = 4096
_MAX_COMMENT_LENGTH = 256
_MAX_EMAIL_LENGTH = 254


def _split_port(entry: str) -> Tuple[str, int | None]:
    m = _PORT_RE.search(entry)
    if m:
        port = int(m.group(1))
        if port < 1 or port > 65535:
            raise ValueError(f"invalid port: {port}")
        return entry[: m.start()], port
    return entry, None


def _is_valid_hostname_labels(entry: str) -> bool:
    if not entry:
        return False
    labels = entry.split(".")
    return all(_HOSTNAME_RE.match(label) for label in labels)


def _is_valid_wildcard_hostname(entry: str) -> bool:
    if not entry.startswith("*."):
        return False
    rest = entry[2:]
    if not rest:
        return False
    return _is_valid_hostname_labels(rest)


def _is_valid_ipv4(entry: str) -> bool:
    try:
        ipaddress.IPv4Address(entry)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


def _validate_host_part(host_part: str) -> None:
    if host_part == "*":
        return
    if _is_valid_wildcard_hostname(host_part):
        return
    if _is_valid_hostname_labels(host_part):
        return
    if _is_valid_ipv4(host_part):
        return
    if host_part.startswith("[") and host_part.endswith("]"):
        try:
            ipaddress.IPv6Address(host_part[1:-1])
            return
        except (ipaddress.AddressValueError, ValueError):
            pass
    raise ValueError(f"invalid host: {host_part}")


def validate_hosts(raw_hosts: str) -> List[str]:
    if not raw_hosts or not raw_hosts.strip():
        raise HTTPException(status_code=422, detail="hosts must not be empty")
    if len(raw_hosts) > _MAX_HOSTS_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"hosts must be <= {_MAX_HOSTS_LENGTH} characters",
        )

    hosts: List[str] = []
    for part in raw_hosts.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        entry = stripped.lower()

        try:
            host_part, port = _split_port(entry)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        if port is not None and host_part == "":
            raise HTTPException(
                status_code=422,
                detail=f"invalid host entry: '{stripped}'",
            )

        try:
            _validate_host_part(host_part)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        if port is not None:
            hosts.append(f"{host_part}:{port}")
        else:
            hosts.append(host_part)

    if not hosts:
        raise HTTPException(status_code=422, detail="hosts must not be empty")
    return hosts


def parse_allowed_hosts(raw_hosts: str) -> List[str]:
    if not raw_hosts:
        return []
    return [h.strip().lower() for h in raw_hosts.split(",") if h.strip()]


def host_matches(requested_host: str, pattern: str) -> bool:
    req = requested_host.lower()
    pat = pattern.lower()

    req_host, req_port = _split_port(req)
    pat_host, pat_port = _split_port(pat)

    if pat_host == "*":
        if pat_port is None:
            return True
        return pat_port == req_port

    if pat_port is not None and pat_port != req_port:
        return False
    if pat_port is None and req_port is not None:
        return False

    if pat_host.startswith("*."):
        suffix = pat_host[1:]
        if not req_host.endswith(suffix):
            return False
        prefix = req_host[: -len(suffix)]
        if not prefix or "." in prefix:
            return False
        return True

    return req_host == pat_host


def validate_email(email: str | None) -> str | None:
    if email is None:
        return None
    stripped = email.strip()
    if not stripped:
        return None
    if len(stripped) > _MAX_EMAIL_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"email must be <= {_MAX_EMAIL_LENGTH} characters",
        )
    if not _EMAIL_RE.match(stripped):
        raise HTTPException(status_code=422, detail="invalid email address")
    return stripped.lower()


def validate_token_hash(token_hash: str) -> None:
    if not _TOKEN_HASH_RE.match(token_hash):
        raise HTTPException(
            status_code=422,
            detail="invalid token hash format (expected 64 hex chars)",
        )


def validate_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    stripped = comment.strip()
    if not stripped:
        return None
    if len(stripped) > _MAX_COMMENT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"comment must be <= {_MAX_COMMENT_LENGTH} characters",
        )
    return stripped
