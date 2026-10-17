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


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.strip().lower()
    return h in {"127.0.0.1", "::1", "localhost"} or h.startswith("127.")
