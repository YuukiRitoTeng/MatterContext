from pathlib import Path

from matter_context.application.runtime_paths import RuntimePaths


def test_isolated_paths_are_created_idempotently(tmp_path: Path) -> None:
    paths = RuntimePaths.isolated(tmp_path / "runtime")

    assert paths.ensure_exists().ensure_exists() is paths
    assert all(path.is_dir() for path in (paths.config, paths.data, paths.attachments, paths.cache, paths.diagnostics))


def test_runtime_environment_overrides_are_honored(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "data"
    attachments = tmp_path / "attachments"
    monkeypatch.setenv("MATTER_CONTEXT_DATA_DIR", str(override))
    monkeypatch.setenv("MATTER_CONTEXT_ATTACHMENTS_DIR", str(attachments))

    paths = RuntimePaths.for_current_platform()

    assert paths.data == override
    assert paths.attachments == attachments


def test_default_paths_do_not_use_current_checkout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    paths = RuntimePaths.for_current_platform()

    assert paths.data != tmp_path
