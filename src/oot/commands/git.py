import subprocess
from typing import List

from oot.config import Project


def git(cfg: Project, args: List[str]):
    cmd = ["git", "-C", cfg.dir] + args

    subprocess.run(cmd)
