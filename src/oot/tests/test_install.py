"""
Tests for the install command.

Repo.get_diff and Repo.apply are mocked — install logic is tested in isolation.
Integration tests use real files on disk but mock the git operations.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oot.commands.install import install, get_metadata
from oot.config import Project, RepoConfig


# --- Fixtures ---


@pytest.fixture
def dirs(tmp_path):
    """Crea kernel_dir y patches_dir con la estructura mínima."""
    kernel = tmp_path / "kernel"
    patches = tmp_path / "patches"
    kernel.mkdir()
    patches.mkdir()
    return {"kernel": kernel, "patches": patches, "tmp": tmp_path}


@pytest.fixture
def project(dirs):
    return Project(
        dir=dirs["tmp"] / ".oot",
        kernel=RepoConfig(
            url="https://example.com/kernel.git", ref="main", dir=dirs["kernel"]
        ),
        patches=RepoConfig(
            url="https://example.com/patches.git", ref="main", dir=dirs["patches"]
        ),
    )


def write_metadata(patches_dir: Path, base_blob: str, files: list[dict]) -> Path:
    meta = {"base_blob": base_blob, "files": files}
    path = patches_dir / "metadata.json"
    path.write_text(json.dumps(meta))
    return path


def mock_repo(get_diff_return: str = "--- diff ---", apply_raises=None):
    """Devuelve un mock de Repo con get_diff y apply controlables."""
    m = MagicMock()
    m.get_diff.return_value = get_diff_return
    if apply_raises:
        m.apply.side_effect = apply_raises
    return m


# --- get_metadata ---


def test_get_metadata_reads_default_path(project, dirs):
    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/foo.c", "status": "new"}]
    )
    meta = get_metadata(project, None)
    assert meta.base_blob == "abc123"
    assert len(meta.files) == 1


def test_get_metadata_reads_custom_path(project, dirs):
    custom = dirs["tmp"] / "custom_meta.json"
    custom.write_text(json.dumps({"base_blob": "xyz", "files": []}))
    meta = get_metadata(project, str(custom))
    assert meta.base_blob == "xyz"


def test_get_metadata_raises_when_missing(project):
    with pytest.raises(FileNotFoundError, match="metadata file not found"):
        get_metadata(project, None)


# --- (status=new) ---


def test_install_copies_new_file(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "sched_petri.c"
    src.parent.mkdir(parents=True)
    src.write_text("// new scheduler\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/sched_petri.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project)

    dst = dirs["kernel"] / "sys" / "kern" / "sched_petri.c"
    assert dst.exists()
    assert dst.read_text() == "// new scheduler\n"


def test_install_creates_parent_dirs(project, dirs):
    src = dirs["patches"] / "sys" / "sys" / "petri_net.h"
    src.parent.mkdir(parents=True)
    src.write_text("// header\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/sys/petri_net.h", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project)

    assert (dirs["kernel"] / "sys" / "sys" / "petri_net.h").exists()


def test_install_skips_new_file_if_identical_exists(project, dirs):
    content = "// same content\n"
    src = dirs["patches"] / "sys" / "kern" / "sched_petri.c"
    src.parent.mkdir(parents=True)
    src.write_text(content)

    dst = dirs["kernel"] / "sys" / "kern" / "sched_petri.c"
    dst.parent.mkdir(parents=True)
    dst.write_text(content)

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/sched_petri.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project)

    # No lanzó excepción y el archivo sigue igual
    assert dst.read_text() == content


def test_install_raises_if_new_file_exists_with_different_content(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "sched_petri.c"
    src.parent.mkdir(parents=True)
    src.write_text("// new version\n")

    dst = dirs["kernel"] / "sys" / "kern" / "sched_petri.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// old version\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/sched_petri.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(FileExistsError, match="already exists in kernel"):
            install(project)


def test_install_new_file_dry_run_does_not_copy(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "sched_petri.c"
    src.parent.mkdir(parents=True)
    src.write_text("// new\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/sched_petri.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project, dry_run=True)

    assert not (dirs["kernel"] / "sys" / "kern" / "sched_petri.c").exists()


# --- (status=modified) ---


def test_install_applies_diff_for_modified_file(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// modified version\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(get_diff_return="--- a\n+++ b\n-original\n+modified\n")
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project)

    repo.apply.assert_called_once()


def test_install_uses_file_base_blob_over_metadata_blob(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// modified\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "global_blob",
        [
            {
                "path": "sys/kern/kern_sched.c",
                "status": "modified",
                "base_blob": "file_blob",
            }
        ],
    )

    repo = mock_repo(get_diff_return="--- diff ---")
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project)

    repo.get_diff.assert_called_once_with("file_blob", src)


def test_install_uses_metadata_blob_when_file_has_none(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// modified\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "global_blob",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(get_diff_return="--- diff ---")
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project)

    repo.get_diff.assert_called_once_with("global_blob", src)


def test_install_skips_modified_when_diff_is_empty(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// same\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// same\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(get_diff_return="   ")  # blank diff
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project)

    repo.apply.assert_not_called()


def test_install_raises_if_modified_target_missing_in_kernel(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// modified\n")

    # No creamos dst en kernel_dir

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(FileNotFoundError, match="not found in kernel repo"):
            install(project)


def test_install_modified_dry_run_passes_to_apply(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// modified\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(get_diff_return="--- diff ---")
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, dry_run=True)

    repo.apply.assert_called_once_with("--- diff ---", dry_run=True)


# --- faltante ---


def test_install_raises_when_patch_file_missing(project, dirs):
    # metadata apunta a un archivo que no existe en patches_dir
    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/nonexistent.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(FileNotFoundError, match="patch file not found"):
            install(project)


# --- fail_fast ---


def test_install_fail_fast_stops_on_first_error(project, dirs):
    for name in ["file_a.c", "file_b.c"]:
        src = dirs["patches"] / "sys" / "kern" / name
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("// content\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [
            {"path": "sys/kern/file_a.c", "status": "new"},
            {"path": "sys/kern/file_b.c", "status": "new"},
        ],
    )

    # file_a ya existe con contenido distinto → FileExistsError
    dst_a = dirs["kernel"] / "sys" / "kern" / "file_a.c"
    dst_a.parent.mkdir(parents=True, exist_ok=True)
    dst_a.write_text("// different\n")

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(FileExistsError):
            install(project, fail_fast=True)

    # file_b no se llegó a procesar
    assert not (dirs["kernel"] / "sys" / "kern" / "file_b.c").exists()


def test_install_no_fail_fast_continues_on_error(project, dirs, caplog):
    import logging

    for name in ["file_a.c", "file_b.c"]:
        src = dirs["patches"] / "sys" / "kern" / name
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("// content\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [
            {"path": "sys/kern/file_a.c", "status": "new"},
            {"path": "sys/kern/file_b.c", "status": "new"},
        ],
    )

    # file_a ya existe con contenido distinto → error, pero continúa
    dst_a = dirs["kernel"] / "sys" / "kern" / "file_a.c"
    dst_a.parent.mkdir(parents=True, exist_ok=True)
    dst_a.write_text("// different\n")

    with (
        patch("oot.commands.install.Repo", return_value=mock_repo()),
        caplog.at_level(logging.ERROR, logger="oot.commands.install"),
    ):
        install(project, fail_fast=False)

    # file_b sí se copió a pesar del error en file_a
    assert (dirs["kernel"] / "sys" / "kern" / "file_b.c").exists()
    assert "file_a.c" in caplog.text


# --- archivos ---


def test_install_processes_all_files(project, dirs):
    files = [
        ("sys/kern/sched_petri.c", "new"),
        ("sys/sys/petri_net.h", "new"),
    ]
    for path, _ in files:
        src = dirs["patches"] / path
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("// content\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": p, "status": s} for p, s in files]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project)

    for path, _ in files:
        assert (dirs["kernel"] / path).exists()
