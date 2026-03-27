from pathlib import Path

from oot.config import Project
from oot.git import Repo, is_git_repo


def fetch(cfg: Project):
    assert cfg.kernel.dir is not None
    cwd = Path(cfg.kernel.dir)
    cwd.expanduser().mkdir(parents=True, exist_ok=True)

    repo = Repo(cwd)

    if is_git_repo(repo):
        print("is git repo")
    else:
        print("is not repo")
