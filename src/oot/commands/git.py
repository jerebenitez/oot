import logging
import subprocess
from typing import List

from oot.config import Project

logger = logging.getLogger(__name__)


def git(cfg: Project, args: List[str]):
    cmd = ["git", "-C", cfg.dir] + args

    logger.debug(f"Running: {' '.join(cmd)}")

    return subprocess.run(cmd)
