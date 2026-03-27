from pathlib import Path
import subprocess


def git(path: Path, *args: str):
    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True,
        text=True,
    )
