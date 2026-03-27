import subprocess

from config import Project


def git(cfg: Project, args: List[str]):
    cmd = ["git", "-C", cfg.dir] + args

    subprocess.run(cmd)
