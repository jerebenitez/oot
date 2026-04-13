import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from oot.errors import ConfigError, FetchError
from oot.git.inspect import is_empty_dir

logger = logging.getLogger(__name__)


def normalize_diff_path(diff: str, path: str | Path) -> str:
    rel = str(path)

    lines = diff.splitlines()
    out = []

    for line in lines:
        if line.startswith("diff --git"):
            out.append(f"diff --git a{rel} b{rel}")
        elif line.startswith("--- "):
            out.append(f"--- a{rel}")
        elif line.startswith("+++ "):
            out.append(f"+++ b{rel}")
        else:
            out.append(line)

    return "\n".join(out) + "\n"


class Repo:
    def __init__(self, path: Path, url: str | None):
        self.path = path
        self.url = url

    def git(self, *args, **kwargs):
        defaults = {"capture_output": True, "text": True}
        return subprocess.run(["git", "-C", self.path, *args], **{**defaults, **kwargs})

    def get_blob(self, blob: str):
        base = self.git("show", blob)
        if base.returncode != 0:
            raise RuntimeError(f"blob {blob} not found")

        return base

    def get_diff(
        self, base_blob: str, target_path: str | Path, rel_path: str | Path
    ) -> str:
        base = self.get_blob(base_blob)

        with tempfile.TemporaryDirectory() as tmp:
            base_file = Path(tmp) / "base"
            base_file.write_text(base.stdout)

            r = self.git("diff", str(base_file), str(target_path))

            if r.returncode not in (0, 1):
                raise RuntimeError(f"git diff failed:\n{r.stderr}")

            diff = r.stdout

            return normalize_diff_path(diff, rel_path)

    def apply(self, diff: str, dry_run: bool = False):
        if dry_run:
            return self.git("apply", "--check", input=diff)

        return self.git("apply", "--3way", input=diff)

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

    def _update_repo(self, ref: str, depth: int | None = None):
        cmd = ["fetch", "origin", ref]
        if depth is not None:
            cmd += ["--depth", str(depth)]

        r = self.git(*cmd)
        if r.returncode != 0:
            raise FetchError(f"git fetch failed:\n{r.stderr.strip()}")

        r = self.git("reset", "--hard", f"origin/{ref}")
        if r.returncode != 0:
            raise FetchError(
                f"git reset --hard origin/{ref} failed:\n{r.stderr.strip()}"
            )

        r = self.git("clean", "-fd")
        if r.returncode != 0:
            raise FetchError(f"git clean failed:\n{r.stderr.strip()}")

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
