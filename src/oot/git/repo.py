import logging
import shutil
import subprocess
from pathlib import Path

from oot.errors import ConfigError, FetchError
from oot.git.inspect import is_empty_dir

logger = logging.getLogger(__name__)


class Repo:
    def __init__(self, path: Path, url: str | None):
        self.path = path
        self.url = url

    def git(self, *args, capture_output: bool = True, check: bool = False):
        return subprocess.run(
            ["git", "-C", self.path, *args],
            capture_output=capture_output,
            text=True,
            check=check,
        )

    def clone(self, ref: str, depth: int = 1, force: bool = False):
        logger.info(f"Cloning repo from {self.url} to {self.path}")

        if force and self.path.exists() and not is_empty_dir(self.path):
            logger.warning(f"Removing existing directory: {self.path}")
            shutil.rmtree(self.path)

        self.path.mkdir(parents=True, exist_ok=True)

        return self.git(
            "clone",
            "--depth",
            str(depth),
            "--branch",
            ref,
            self.url,
            self.path,
            capture_output=False,
        )

    def update(self, ref: str, depth: int = 1):
        origin = self.get_origin()
        if origin == self.url:
            return self._update_repo(ref, depth)
        else:
            raise ConfigError(
                f"{self} is a git repo with a different origin than the one in the config.\n"
                f"      Config  : {self.url}\n"
                f"      Current : {origin}\n"
                f"      To use this repo, update 'url' in your config file."
            )

    def _update_repo(self, ref: str, depth: int = 1):
        r = self.git("fetch", "--all")

        if r.returncode != 0:
            raise FetchError(f"git fetch failed:\n{r.stderr.strip()}")

        r = self.git("checkout", ref)

        if r.returncode != 0:
            raise FetchError(f"git checkout {ref} failed:\n{r.stderr.strip()}")

        r = self.git("symbolic-ref", "--quiet", "HEAD")

        if r.returncode == 0:
            cmd = ["pull", "--ff-only"]

            if depth:
                cmd += ["--depth", str(depth)]

            r = self.git(*cmd)
            if r.returncode != 0:
                logger.warning(
                    f"git pull --ff-only failed (you may have local changes):\n"
                    f"{r.stderr.strip()}"
                )

        logger.info(f"Updated to {ref}")

    def is_git_repo(self) -> bool:
        result = self.git("rev-parse", "--is-inside-work-tree")
        return result.returncode == 0

    def get_origin(self):
        result = self.git("remote", "get-url", "origin")

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    def set_origin(self, origin):
        return self.git("remote", "add", "origin", origin, check=True)
