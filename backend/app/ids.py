import hashlib
from pathlib import Path


def media_id_for_path(path: Path) -> str:
    """Stable short id derived from the absolute normalized path."""
    normalized = str(path.resolve()).replace("\\", "/").lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]
