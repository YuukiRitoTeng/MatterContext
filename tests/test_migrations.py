from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from matter_context.storage.database import Database, migration_script_location, upgrade_database


def test_migration_scripts_resolve_from_the_storage_package() -> None:
    with migration_script_location() as location:
        assert (location / "env.py").is_file()
        assert (location / "script.py.mako").is_file()
        assert (location / "versions" / "0001_initial_domain.py").is_file()


def test_alembic_creates_complete_initial_schema(tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'fresh.sqlite3'}")
    upgrade_database(str(database.engine.url))

    assert {"matters", "sources", "content_blocks", "claims", "source_references", "review_decisions", "processing_runs", "case_brief_versions"} <= set(inspect(database.engine).get_table_names())


def test_alembic_honors_database_url_environment_override(monkeypatch, tmp_path) -> None:
    target = tmp_path / "environment.sqlite3"
    monkeypatch.setenv("MATTER_CONTEXT_DATABASE_URL", f"sqlite:///{target}")
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    assert "matters" in inspect(Database.from_url(f"sqlite:///{target}").engine).get_table_names()
