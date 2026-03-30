from pathlib import Path


def is_empty_dir(path: Path) -> bool:
    p = Path(path)

    if not p.exists():
        return True  # o False según tu criterio

    return not any(p.iterdir())
