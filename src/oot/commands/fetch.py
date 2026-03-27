import logging
import shutil
from pathlib import Path

from oot.config import Project
from oot.errors import RepoStateError
from oot.git import Repo, clone, is_empty_dir, is_git_repo

logger = logging.getLogger(__name__)


def fetch(cfg: Project, force: bool):
    assert cfg.kernel.dir is not None
    cwd = Path(cfg.kernel.dir).expanduser()
    cwd.mkdir(parents=True, exist_ok=True)

    repo = Repo(cwd)

    if force:
        if cwd.exists() and not is_empty_dir(cwd):
            logger.warning(f"Removing existing directory: {cwd}")
            shutil.rmtree(cwd)

        clone(
            url=cfg.kernel.url,
            path=cwd,
            depth=cfg.kernel.depth,
            ref=cfg.kernel.ref,
        )
    elif is_git_repo(repo):
        print("is git repo")
    elif is_empty_dir(repo.path):
        logger.debug("Directory is empty, cloning inside...")
        clone(url=cfg.kernel.url, path=cwd, depth=cfg.kernel.depth, ref=cfg.kernel.ref)
    else:
        if cfg.kernel.url is None:
            logger.info(
                "Directory is not empty, and url is not set. Nothing to do here."
            )
        else:
            raise RepoStateError(
                f"{cwd} exists, is not empty, and is not a git repository.\n\n"
                f"Configured URL: {cfg.kernel.url}\n\n"
                "Refusing to clone into a non-empty directory.\n\n"
                "Options:\n"
                "  • Remove the directory and run 'oot fetch' again\n"
                "  • Remove 'kernel.url' from the config to use the existing directory\n"
                "  • Use '--force' to overwrite the directory (WARNING: deletes contents)"
            )
