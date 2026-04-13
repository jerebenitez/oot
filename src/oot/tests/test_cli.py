"""
Tests for the install command.

Repo.get_diff y Repo.apply están mockeados — la lógica de install se testea en aislamiento.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from oot.commands.install import install, get_metadata, resolvers
from oot.config import Project, RepoConfig


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dirs(tmp_path):
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


def make_apply_result(returncode: int = 0, stderr: str = ""):
    r = MagicMock()
    r.returncode = returncode
    r.stderr = stderr
    return r


def mock_repo(diff: str = "--- diff ---", apply_rc: int = 0):
    """
    Devuelve un mock de Repo.

    - get_diff devuelve `diff`
    - apply devuelve un resultado con returncode=apply_rc en todas las llamadas
    """
    m = MagicMock()
    m.get_diff.return_value = diff
    m.apply.return_value = make_apply_result(apply_rc)
    return m


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def test_resolver_abort_returns_abort():
    from oot.commands.install import Action

    assert resolvers["abort"]("any/path") == Action.ABORT


def test_resolver_skip_returns_skip():
    from oot.commands.install import Action

    assert resolvers["skip"]("any/path") == Action.SKIP


def test_resolver_force_returns_continue():
    from oot.commands.install import Action

    assert resolvers["force"]("any/path") == Action.CONTINUE


# ---------------------------------------------------------------------------
# status=new — happy path
# ---------------------------------------------------------------------------


def test_install_copies_new_file(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "sched_petri.c"
    src.parent.mkdir(parents=True)
    src.write_text("// new scheduler\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/sched_petri.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project, resolvers["abort"])

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
        install(project, resolvers["abort"])

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
        install(project, resolvers["abort"])

    assert dst.read_text() == content


def test_install_new_file_dry_run_does_not_copy(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "sched_petri.c"
    src.parent.mkdir(parents=True)
    src.write_text("// new\n")

    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/sched_petri.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project, resolvers["abort"], dry_run=True)

    assert not (dirs["kernel"] / "sys" / "kern" / "sched_petri.c").exists()


# ---------------------------------------------------------------------------
# status=new — conflictos
# ---------------------------------------------------------------------------


def test_install_new_conflict_resolver_skip(project, dirs):
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
        install(project, resolvers["skip"])

    assert dst.read_text() == "// old version\n"


def test_install_new_conflict_resolver_force_overwrites(project, dirs):
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
        install(project, resolvers["force"])

    assert dst.read_text() == "// new version\n"


def test_install_new_conflict_resolver_abort_stops_install(project, dirs):
    for name in ["file_a.c", "file_b.c"]:
        src = dirs["patches"] / "sys" / "kern" / name
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("// new\n")

    dst_a = dirs["kernel"] / "sys" / "kern" / "file_a.c"
    dst_a.parent.mkdir(parents=True, exist_ok=True)
    dst_a.write_text("// old\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [
            {"path": "sys/kern/file_a.c", "status": "new"},
            {"path": "sys/kern/file_b.c", "status": "new"},
        ],
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        install(project, resolvers["abort"])

    assert not (dirs["kernel"] / "sys" / "kern" / "file_b.c").exists()


# ---------------------------------------------------------------------------
# status=modified — happy path
# ---------------------------------------------------------------------------


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

    repo = mock_repo(diff="--- a\n+++ b\n-original\n+modified\n")
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["abort"])

    repo.apply.assert_called_once_with(
        "--- a\n+++ b\n-original\n+modified\n", dry_run=False
    )


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

    repo = mock_repo()
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["abort"])

    repo.get_diff.assert_called_once_with("file_blob", src, "sys/kern/kern_sched.c")


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

    repo = mock_repo()
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["abort"])

    repo.get_diff.assert_called_once_with("global_blob", src, "sys/kern/kern_sched.c")


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

    repo = mock_repo(diff="   ")
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["abort"])

    repo.apply.assert_not_called()


def test_install_raises_if_modified_target_missing_in_kernel(project, dirs):
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// modified\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(FileNotFoundError, match="not found in kernel repo"):
            install(project, resolvers["abort"])


def test_install_modified_dry_run_calls_apply_with_dry_run(project, dirs):
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

    repo = mock_repo()
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["abort"], dry_run=True)

    repo.apply.assert_called_once_with("--- diff ---", dry_run=True)


# ---------------------------------------------------------------------------
# status=modified — conflictos
# ---------------------------------------------------------------------------


def test_install_modified_conflict_resolver_skip(project, dirs):
    """apply falla + resolver skip → no se reintenta."""
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// patch\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(apply_rc=1)
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["skip"])

    repo.apply.assert_called_once()


def test_install_modified_conflict_resolver_abort(project, dirs):
    """apply falla + resolver abort → install se detiene sin procesar más archivos."""
    for name in ["kern_sched.c", "vm_pager.c"]:
        src = dirs["patches"] / "sys" / "kern" / name
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("// patch\n")
        dst = dirs["kernel"] / "sys" / "kern" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [
            {"path": "sys/kern/kern_sched.c", "status": "modified"},
            {"path": "sys/kern/vm_pager.c", "status": "modified"},
        ],
    )

    # Solo el primer apply falla
    results = [make_apply_result(1), make_apply_result(0)]
    repo = MagicMock()
    repo.get_diff.return_value = "--- diff ---"
    repo.apply.side_effect = results

    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["abort"])

    repo.apply.assert_called_once()


def test_install_modified_conflict_resolver_force_retries_apply(project, dirs):
    """apply falla + resolver force → se reintenta apply sin dry_run."""
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// patch\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    results = [make_apply_result(1), make_apply_result(0)]
    repo = MagicMock()
    repo.get_diff.return_value = "--- diff ---"
    repo.apply.side_effect = results

    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["force"])

    assert repo.apply.call_count == 2
    assert repo.apply.call_args_list == [
        call("--- diff ---", dry_run=False),
        call("--- diff ---"),
    ]


def test_install_modified_force_retry_failure_raises(project, dirs):
    """apply falla + force + reintento también falla → RuntimeError."""
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// patch\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(apply_rc=1)
    with patch("oot.commands.install.Repo", return_value=repo):
        with pytest.raises(RuntimeError, match=r"force apply failed .*"):
            install(project, resolvers["force"])


def test_install_modified_dry_run_conflict_does_not_retry(project, dirs):
    """En dry_run, apply falla pero no se reintenta aunque el resolver sea force."""
    src = dirs["patches"] / "sys" / "kern" / "kern_sched.c"
    src.parent.mkdir(parents=True)
    src.write_text("// patch\n")

    dst = dirs["kernel"] / "sys" / "kern" / "kern_sched.c"
    dst.parent.mkdir(parents=True)
    dst.write_text("// original\n")

    write_metadata(
        dirs["patches"],
        "abc123",
        [{"path": "sys/kern/kern_sched.c", "status": "modified"}],
    )

    repo = mock_repo(apply_rc=1)
    with patch("oot.commands.install.Repo", return_value=repo):
        install(project, resolvers["force"], dry_run=True)

    repo.apply.assert_called_once_with("--- diff ---", dry_run=True)


# ---------------------------------------------------------------------------
# Patch file faltante
# ---------------------------------------------------------------------------


def test_install_raises_when_patch_file_missing(project, dirs):
    write_metadata(
        dirs["patches"], "abc123", [{"path": "sys/kern/nonexistent.c", "status": "new"}]
    )

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(FileNotFoundError, match="patch file not found"):
            install(project, resolvers["abort"])


# ---------------------------------------------------------------------------
# fail_fast
# ---------------------------------------------------------------------------


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

    def exploding_resolver(path):
        raise RuntimeError(f"unexpected error for {path}")

    dst_a = dirs["kernel"] / "sys" / "kern" / "file_a.c"
    dst_a.parent.mkdir(parents=True, exist_ok=True)
    dst_a.write_text("// different\n")

    with patch("oot.commands.install.Repo", return_value=mock_repo()):
        with pytest.raises(RuntimeError):
            install(project, exploding_resolver, fail_fast=True)

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

    def exploding_resolver(path):
        raise RuntimeError(f"unexpected error for {path}")

    dst_a = dirs["kernel"] / "sys" / "kern" / "file_a.c"
    dst_a.parent.mkdir(parents=True, exist_ok=True)
    dst_a.write_text("// different\n")

    with (
        patch("oot.commands.install.Repo", return_value=mock_repo()),
        caplog.at_level(logging.ERROR, logger="oot.commands.install"),
    ):
        install(project, exploding_resolver, fail_fast=False)

    assert (dirs["kernel"] / "sys" / "kern" / "file_b.c").exists()
    assert "file_a.c" in caplog.text


# ---------------------------------------------------------------------------
# Múltiples archivos
# ---------------------------------------------------------------------------


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
        install(project, resolvers["abort"])

    for path, _ in files:
        assert (dirs["kernel"] / path).exists()
