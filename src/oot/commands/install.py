import filecmp
import logging
import shutil
from enum import Enum
from pathlib import Path
from typing import Literal

from oot.config import Project
from oot.git.repo import Repo
from oot.metadata import Metadata, FileMetadata

logger = logging.getLogger(__name__)

OnConflict = Literal["force", "skip", "abort"]


class Action(Enum):
    SKIP = "skip"
    CONTINUE = "continue"
    ABORT = "abort"


resolvers = {
    "abort": lambda _: Action.ABORT,
    "skip": lambda _: Action.SKIP,
    "force": lambda _: Action.CONTINUE,
}


class Context:
    def __init__(self, repo, patches_dir, kernel_dir, resolver, dry_run):
        self.repo = repo
        self.patches_dir = patches_dir
        self.kernel_dir = kernel_dir
        self.resolve = resolver
        self.dry_run = dry_run


def install(
    cfg: Project,
    resolver,
    metadata_path: str | None = None,
    dry_run: bool = False,
    fail_fast: bool = True,
):
    assert isinstance(cfg.kernel.dir, Path)
    assert isinstance(cfg.patches.dir, Path)

    metadata = get_metadata(cfg, metadata_path)
    repo = Repo(cfg.kernel.dir, cfg.kernel.url)

    ctx = Context(repo, cfg.patches.dir, cfg.kernel.dir, resolver, dry_run)

    handlers = {
        "modified": _install_modified,
        "new": _install_new,
        "deleted": _install_deleted,
    }

    for file in metadata.files:
        base_blob = file.base_blob if file.base_blob else metadata.base_blob

        handler = handlers.get(file.status)
        if handler is None:
            raise ValueError(f"unknown status: {file.status}")

        try:
            result = handler(ctx, file, base_blob)

            if result == Action.SKIP:
                logger.info("Skipping %s", file.path)
                continue
            elif result == Action.ABORT:
                logger.info("Aborting install")
                return

            ctx.repo.git("add", "-A")
            ctx.repo.git("commit", "-m", "chore: installed patches to kernel")

        except Exception as e:
            if fail_fast:
                raise
            logger.error("Failed processing %s: %s", file.path, e)


def _install_deleted(
    ctx: Context,
    file: FileMetadata,
    _: str,
):
    dst = ctx.kernel_dir / file.path

    if not dst.exists():
        # install should be somewhat idempotent, if the file doesn't exist, our job is done
        pass
    # directories are not handled in order to follow git's logic
    elif dst.is_file() or dst.is_symlink():
        if not dst.resolve().is_relative_to(ctx.kernel_dir.resolve()):
            raise RuntimeError(f"Path escapes kernel dir: {dst}")
        dst.unlink()
    else:
        raise RuntimeError(f"Unsupported file type for path: {dst}")


def _install_modified(
    ctx: Context,
    file: FileMetadata,
    base_blob: str,
):
    src = ctx.patches_dir / file.path
    dst = ctx.kernel_dir / file.path

    if not src.is_file():
        raise FileNotFoundError(f"File {file.path} not found in patches repo")

    if not dst.is_file():
        raise FileNotFoundError(f"File {file.path} not found in kernel repo")

    diff = ctx.repo.get_diff(base_blob, src, file.path)

    if not diff.strip():
        logger.debug("No diff for %s, skipping", file.path)
        return

    # Check conflicts first
    r = ctx.repo.apply(diff, dry_run=ctx.dry_run)
    if r.returncode != 0:
        action = ctx.resolve(file.path)

        if action == Action.SKIP or action == Action.ABORT:
            return action

        if not ctx.dry_run:
            r = ctx.repo.apply(diff)
            if r.returncode != 0:
                raise RuntimeError(f"force apply failed for {file.path}:\n{r.stderr}")


def _install_new(
    ctx: Context,
    file: FileMetadata,
    _: str,
):
    src = ctx.patches_dir / file.path
    dst = ctx.kernel_dir / file.path

    if not src.is_file():
        raise FileNotFoundError(f"patch file not found: {file.path}")

    if dst.exists():
        if filecmp.cmp(src, dst, shallow=False):
            logger.debug("File identical, skipping: %s", file.path)
            return

        action = ctx.resolve(file.path)

        if action == Action.SKIP or action == Action.ABORT:
            return action

        # force → overwrite
    if not ctx.dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

    logger.debug("Installed %s", file.path)


def get_metadata(cfg: Project, metadata_path: str | Path | None):
    metadata_path = (
        Path(metadata_path)
        if metadata_path is not None
        else cfg.patches.dir / "metadata.json"
    )

    if not metadata_path.is_file():
        raise FileNotFoundError(f"metadata file not found: {metadata_path}")

    return Metadata.model_validate_json(metadata_path.read_text())
