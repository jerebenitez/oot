from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)


def clone(url: str, path: Path, depth: int, ref: str):
    logger.info(f"Cloning repo from {url} to {path}")

    return subprocess.run(
        ["git", "clone", "--depth", str(depth), "--branch", ref, url, path],
        check=True,
    )
