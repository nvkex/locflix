from __future__ import annotations

import json
import threading
from pathlib import Path

_lock = threading.Lock()


def _path(data_dir: Path) -> Path:
    return data_dir / "lan_known_seeders.json"


def load_known_seeders(data_dir: Path) -> list[tuple[str, int]]:
    path = _path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[tuple[str, int]] = []
    if not isinstance(raw, list):
        return []
    for item in raw:
        if not isinstance(item, dict):
            continue
        host = str(item.get("host") or "").strip()
        try:
            port = int(item.get("port") or 8787)
        except (TypeError, ValueError):
            continue
        if host:
            out.append((host, port))
    return out


def remember_seeder(data_dir: Path, host: str, port: int) -> None:
    host = host.strip()
    if not host:
        return
    path = _path(data_dir)
    with _lock:
        known = load_known_seeders(data_dir)
        entry = (host, int(port))
        known = [item for item in known if item != entry]
        known.insert(0, entry)
        known = known[:20]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([{"host": h, "port": p} for h, p in known], indent=2),
            encoding="utf-8",
        )
