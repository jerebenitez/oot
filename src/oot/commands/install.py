import filecmp
import logging
import shutil
from pathlib import Path

from oot.config import Project
from oot.git.repo import Repo
from oot.metadata import Metadata

logger = logging.getLogger(__name__)


def install(
    cfg: Project,
    metadata_path: str | None = None,
    dry_run: bool = False,
    fail_fast: bool = True,
):
    assert isinstance(cfg.kernel.dir, Path)
    assert isinstance(cfg.patches.dir, Path)

    metadata = get_metadata(cfg, metadata_path)
    repo = Repo(cfg.kernel.dir, cfg.kernel.url)

    for file in metadata.files:
        src_path = cfg.patches.dir / file.path
        dst_path = cfg.kernel.dir / file.path

        if not src_path.is_file():
            raise FileNotFoundError(f"patch file not found: {file.path}")

        try:
            if file.status == "modified":
                if not dst_path.is_file():
                    raise FileNotFoundError(
                        f"file {file.path} not found in kernel repo"
                    )
                else:
                    diff = repo.get_diff(
                        file.base_blob if file.base_blob else metadata.base_blob,
                        src_path,
                    )

                    if not diff.strip():
                        continue

                    repo.apply(diff, dry_run=dry_run)

            elif file.status == "new":
                if dst_path.exists():
                    if filecmp.cmp(src_path, dst_path, shallow=False):
                        continue

                    raise FileExistsError(f"file already exists in kernel: {file.path}")

                if not dry_run:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src_path, dst_path)

            else:
                # Should never reach this
                raise ValueError(f"unknown status: {file.status}")
        except Exception as e:
            if fail_fast:
                raise
            else:
                logger.error(f"failed processing: {file.path}: {e}")
                continue


def get_metadata(cfg: Project, metadata_path: str | None):
    metadata_dir = (
        Path(metadata_path)
        if metadata_path is not None
        else cfg.patches.dir / "metadata.json"
    )

    if not metadata_dir.is_file():
        raise FileNotFoundError(f"metadata file not found: {metadata_dir}")

    return Metadata.model_validate_json(metadata_dir.read_text())
