import filecmp
import logging
from pathlib import Path

from oot.config import Project
from oot.git.repo import Repo
from oot.metadata import FileMetadata, Metadata

logger = logging.getLogger(__name__)

# Files in patches_dir that are never part of the snapshot
_EXCLUDED = {"metadata.json"}


def _files_on_disk(patches_dir: Path) -> set[str]:
    """All non-excluded files currently on disk in patches_dir (relative)."""
    result = set()
    for p in patches_dir.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(patches_dir))
            if rel not in _EXCLUDED and ".git" not in Path(rel).parts:
                result.add(rel)
    return result


def _compute_entries(
    kernel_repo: Repo,
    patches_repo: Repo,
    existing: dict[str, FileMetadata],
) -> list[FileMetadata]:
    """
    Produce a consolidated FileMetadata list by comparing the current state of
    patches_dir against the kernel HEAD.

    Consolidation rules
    -------------------
    File on disk in patches_dir:
      - Not in kernel                         → "new"
      - In kernel, identical content          → drop (no patch needed)
      - In kernel, different content          → "modified" (preserve base_blob)

    File previously tracked (in existing) but no longer on disk:
      - Was "new" in prior metadata           → drop entirely (we added it, we removed it)
      - Was "modified" or "deleted", in kernel → "deleted"
      - Was "modified" or "deleted", not in kernel → drop (already gone)
    """
    on_disk = _files_on_disk(patches_repo.path)
    entries: list[FileMetadata] = []

    for rel in on_disk:
        blob = kernel_repo.get_blob_hash(rel)

        if blob is None:
            # File not in kernel at all → new
            entries.append(FileMetadata(path=rel, base_blob=None, status="new"))
        else:
            # Preserve the base_blob established when the file was first captured
            # so that install can still compute a valid diff against the original.
            prev = existing.get(rel)
            if prev is not None and prev.status == "modified":
                file_base_blob = prev.base_blob  # may be None (uses global)
            else:
                file_base_blob = blob

            if filecmp.cmp(
                patches_repo.path / rel, kernel_repo.path / rel, shallow=False
            ):
                logger.debug("Identical to kernel, dropping: %s", rel)
            else:
                entries.append(
                    FileMetadata(path=rel, base_blob=file_base_blob, status="modified")
                )

    # Previously tracked files that disappeared from disk
    for rel, prev in existing.items():
        if rel in on_disk:
            continue  # already handled above

        if prev.status == "new":
            # We added it, now it's gone → net effect is nothing
            logger.debug("New file removed, consolidating away: %s", rel)
            continue

        blob = kernel_repo.get_blob_hash(rel)
        if blob is None:
            # Not in kernel either → nothing to restore, drop
            logger.debug("Removed file absent from kernel, consolidating away: %s", rel)
        else:
            entries.append(FileMetadata(path=rel, base_blob=None, status="deleted"))

    return sorted(entries, key=lambda e: e.path)


def sync(cfg: Project, message: str, dry_run: bool = False):
    assert isinstance(cfg.kernel.dir, Path)
    assert isinstance(cfg.patches.dir, Path)

    patches_dir = cfg.patches.dir

    patches_repo = Repo(cfg.patches.dir, None)
    kernel_repo = Repo(cfg.kernel.dir, cfg.kernel.url)

    if not patches_repo.is_git_repo():
        raise RuntimeError(f"{patches_dir} is not a git repository")

    # Load existing metadata to enable consolidation
    metadata_path = patches_dir / "metadata.json"
    existing: dict[str, FileMetadata] = {}

    if metadata_path.is_file():
        old = Metadata.model_validate_json(metadata_path.read_text())
        existing = {f.path: f for f in old.files}

    base_blob = kernel_repo.get_head_blob()
    new_entries = _compute_entries(kernel_repo, patches_repo, existing)
    new_metadata = Metadata(base_blob=base_blob, files=new_entries)

    if dry_run:
        print(new_metadata.model_dump_json(indent=2))
        return

    metadata_path.write_text(new_metadata.model_dump_json(indent=2) + "\n")
    logger.info("Wrote %s", metadata_path)

    patches_repo.git("add", "-A", check=True)

    # Only commit if there is something staged
    r = patches_repo.git("diff", "--cached", "--quiet")
    if r.returncode == 0:
        logger.info("Nothing to commit")
        return

    patches_repo.git("commit", "-m", message, check=True)
    logger.info("Committed: %s", message)
