from pathlib import Path


def is_under_roots(path: Path, roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False

    for root in roots:
        try:
            resolved_root = root.resolve()
        except OSError:
            continue
        if resolved == resolved_root or resolved_root in resolved.parents:
            return True
    return False
