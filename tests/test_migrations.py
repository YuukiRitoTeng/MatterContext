from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from matter_context.storage.database import Database, migration_script_location, upgrade_database


def test_migration_scripts_resolve_from_the_storage_package() -> None:
    with migration_script_location() as location:
        assert (location / "env.py").is_file()
        assert (location / "script.py.mako").is_file()
        assert (location / "versions" / "0001_initial_domain.py").is_file()
        assert (location / "versions" / "0002_narrative_update_type.py").is_file()
        assert (location / "versions" / "0003_document_ingestion.py").is_file()


def test_alembic_creates_complete_initial_schema(tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'fresh.sqlite3'}")
    upgrade_database(str(database.engine.url))

    assert {"matters", "sources", "content_blocks", "claims", "source_references", "review_decisions", "processing_runs", "case_brief_versions"} <= set(inspect(database.engine).get_table_names())
    source_columns = {column["name"] for column in inspect(database.engine).get_columns("sources")}
    block_columns = {column["name"] for column in inspect(database.engine).get_columns("content_blocks")}
    run_columns = {column["name"] for column in inspect(database.engine).get_columns("processing_runs")}
    assert {"update_type", "duplicate_of_id"} <= source_columns
    assert {"page", "paragraph", "character_start", "character_end"} <= block_columns
    assert {"parser_name", "parser_version", "duration_ms"} <= run_columns


def test_upgrade_from_0001_preserves_populated_chinese_sources_and_nullable_update_type(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'populated-0001.sqlite3'}"
    with migration_script_location() as location:
        config = Config()
        config.set_main_option("sqlalchemy.url", url)
        config.set_main_option("script_location", str(location))
        command.upgrade(config, "0001")

        database = Database.from_url(url)
        original_text = "当事人称：2026年8月24日已支付全部款项。\n请保留原文。"
        correction_text = "更正：付款日期为2026年8月23日。"
        with database.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO matters (identifier, title, reference, description, status, created_at, updated_at) "
                "VALUES (:identifier, :title, :reference, :description, :status, :created_at, :updated_at)"
            ), {
                "identifier": "matter-0001", "title": "中文案件", "reference": "MC-中文", "description": "迁移前案件",
                "status": "active", "created_at": "2026-08-24 10:00:00", "updated_at": "2026-08-24 10:00:00",
            })
            for identifier, source_text, correction_of_id in (
                ("source-original", original_text, None),
                ("source-correction", correction_text, "source-original"),
            ):
                connection.execute(text(
                    "INSERT INTO sources (identifier, matter_id, kind, provenance, payload_sha256, text, attachment_path, "
                    "original_filename, media_type, correction_of_id, ingestion_status, extraction_status, created_at) "
                    "VALUES (:identifier, :matter_id, :kind, :provenance, :payload_sha256, :text, NULL, NULL, NULL, "
                    ":correction_of_id, :ingestion_status, :extraction_status, :created_at)"
                ), {
                    "identifier": identifier, "matter_id": "matter-0001", "kind": "narrative_update",
                    "provenance": "attorney_provided", "payload_sha256": "a" * 64, "text": source_text,
                    "correction_of_id": correction_of_id, "ingestion_status": "ready",
                    "extraction_status": "not_started", "created_at": "2026-08-24 10:01:00",
                })

        command.upgrade(config, "0003_document_ingestion")

    with Database.from_url(url).engine.connect() as connection:
        matter = connection.execute(text("SELECT identifier, title, reference FROM matters")).mappings().one()
        sources = connection.execute(text(
            "SELECT identifier, matter_id, text, correction_of_id, update_type, duplicate_of_id FROM sources ORDER BY identifier"
        )).mappings().all()
    assert dict(matter) == {"identifier": "matter-0001", "title": "中文案件", "reference": "MC-中文"}
    assert [dict(source) for source in sources] == [
        {
            "identifier": "source-correction", "matter_id": "matter-0001", "text": correction_text,
            "correction_of_id": "source-original", "update_type": None, "duplicate_of_id": None,
        },
        {
            "identifier": "source-original", "matter_id": "matter-0001", "text": original_text,
            "correction_of_id": None, "update_type": None, "duplicate_of_id": None,
        },
    ]


def test_alembic_honors_database_url_environment_override(monkeypatch, tmp_path) -> None:
    target = tmp_path / "environment.sqlite3"
    monkeypatch.setenv("MATTER_CONTEXT_DATABASE_URL", f"sqlite:///{target}")
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    assert "matters" in inspect(Database.from_url(f"sqlite:///{target}").engine).get_table_names()
