from pathlib import Path

from oot.git import git, Repo


def is_git_repo(repo: Repo) -> bool:
    result = git(repo.path, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0


def get_origin(repo: Repo) -> str | None:
    result = git(repo.path, "remote", "get-url", "origin")

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def is_empty_dir(path: str) -> bool:
    p = Path(path)

    if not p.exists():
        return True  # o False según tu criterio

    return not any(p.iterdir())
