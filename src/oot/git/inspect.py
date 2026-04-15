from pathlib import Path


def is_empty_dir(path: Path) -> bool:
    p = Path(path)

    if not p.exists():
        return True

    return not any(p.iterdir())
