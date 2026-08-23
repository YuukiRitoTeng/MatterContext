"""SQLite engine and runtime-path bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from matter_context.application.runtime_paths import RuntimePaths


@dataclass(frozen=True, slots=True)
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def from_url(cls, url: str) -> "Database":
        engine = create_engine(url, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(engine, "connect")
            def _enable_foreign_keys(connection: object, _: object) -> None:
                cursor = connection.cursor()  # type: ignore[union-attr]
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        return cls(engine=engine, session_factory=sessionmaker(engine, expire_on_commit=False))


def database_for_runtime_paths(paths: RuntimePaths) -> Database:
    paths.ensure_exists()
    database = Database.from_url(f"sqlite:///{paths.data / 'matter-context.sqlite3'}")
    upgrade_database(str(database.engine.url))
    return database


@contextmanager
def migration_script_location() -> Iterator[Path]:
    """Yield a filesystem location for Alembic's packaged migration scripts.

    Alembic loads ``env.py`` and revision modules from a directory, while
    application resources are not necessarily directories (notably in a
    onefile executable). ``as_file`` supplies a temporary directory when the
    package loader needs one and leaves normal installed/source packages alone.
    """
    migrations = files("matter_context.storage.migrations")
    with as_file(migrations) as location:
        yield location


def upgrade_database(url: str) -> None:
    """Apply packaged schema migrations before repositories open a database."""
    with migration_script_location() as script_location:
        # Do not load the repository-level alembic.ini at runtime: it is not a
        # package resource and does not exist in a frozen onefile layout.
        config = Config()
        config.set_main_option("sqlalchemy.url", url)
        config.set_main_option("script_location", str(script_location))
        command.upgrade(config, "head")
