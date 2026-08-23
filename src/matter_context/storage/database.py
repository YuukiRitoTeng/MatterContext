"""SQLite engine and runtime-path bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
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


def upgrade_database(url: str) -> None:
    """Apply packaged schema migrations before repositories open a database."""
    config_path = Path(__file__).resolve().parents[3] / "alembic.ini"
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", url)
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    command.upgrade(config, "head")
