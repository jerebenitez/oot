import logging
from pathlib import Path

import click

from oot.config import Project
from oot.errors import RepoStateError
from oot.git import Repo, is_empty_dir

logger = logging.getLogger(__name__)


def fetch(cfg: Project, force: bool):
    assert cfg.kernel.dir is not None
    assert isinstance(cfg.kernel.dir, Path)
    repo = Repo(cfg.kernel.dir, cfg.kernel.url)

    if force:
        return repo.clone(depth=cfg.kernel.depth, ref=cfg.kernel.ref, force=True)

    if repo.is_git_repo():
        if repo.get_origin() is None:
            if click.confirm(
                f"\n {repo} is a git repo with no remote origin.\n"
                f"  Do you want to add {repo.url} as origin and continue?"
            ):
                repo.set_origin(repo.url)
            else:
                logger.info(
                    "Cancelled. Update 'dir' in your config file to point to a different directory."
                )
                return

        return repo.update(ref=cfg.kernel.ref, depth=cfg.kernel.depth)

    if is_empty_dir(repo.path):
        logger.debug("Directory is empty, cloning inside...")
        return repo.clone(depth=cfg.kernel.depth, ref=cfg.kernel.ref)

    if repo.url is None:
        logger.info("Directory is not empty, and url is not set. Nothing to do here.")
        return
    else:
        raise RepoStateError(
            f"{repo.path} exists, is not empty, and is not a git repository.\n\n"
            f"Configured URL: {repo.url}\n\n"
            "Refusing to clone into a non-empty directory.\n\n"
            "Options:\n"
            "  • Remove the directory and run 'oot fetch' again\n"
            "  • Remove 'kernel.url' from the config to use the existing directory\n"
            "  • Use '--force' to overwrite the directory (WARNING: deletes contents)"
        )
