from __future__ import annotations

import socket


def primary_lan_ip() -> str:
    """Best-effort LAN IPv4 used for advertising this seeder."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip:
                return ip
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def default_share_name() -> str:
    try:
        return socket.gethostname() or "Locflix Seeder"
    except OSError:
        return "Locflix Seeder"


def local_hostname() -> str:
    try:
        name = socket.gethostname().strip()
        return name or "Locflix"
    except OSError:
        return "Locflix"


def resolve_hostname(ip: str | None) -> str | None:
    """Best-effort reverse DNS for a client IP (short host label)."""
    if not ip or is_loopback_host(ip):
        return None
    try:
        host, _aliases, _addrs = socket.gethostbyaddr(ip)
    except OSError:
        return None
    label = (host or "").split(".")[0].strip()
    return label or None


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.strip().lower()
    return h in {"127.0.0.1", "::1", "localhost"} or h.startswith("127.")


def broadcast_targets(ip: str | None = None) -> list[str]:
    """IPv4 broadcast addresses to try (subnet /24 + limited broadcast)."""
    targets = ["255.255.255.255"]
    addr = ip or primary_lan_ip()
    parts = addr.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        targets.insert(0, f"{parts[0]}.{parts[1]}.{parts[2]}.255")
    # de-dupe, keep order
    seen: set[str] = set()
    ordered: list[str] = []
    for item in targets:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
