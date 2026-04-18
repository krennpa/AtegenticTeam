from pathlib import Path
from typing import Generator
import sqlite3

from sqlmodel import SQLModel, Session, create_engine

from ..core.config import settings


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _resolve_database_url(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        return database_url

    sqlite_path = database_url.replace("sqlite:///", "", 1)
    if sqlite_path == ":memory:":
        return database_url

    db_file = Path(sqlite_path)
    if not db_file.is_absolute():
        db_file = (BACKEND_DIR / db_file).resolve()
    return f"sqlite:///{db_file.as_posix()}"


def _ensure_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return

    sqlite_path = database_url.replace("sqlite:///", "", 1)
    if sqlite_path == ":memory:":
        return

    db_file = Path(sqlite_path)
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    db_file.parent.mkdir(parents=True, exist_ok=True)


RESOLVED_DATABASE_URL = _resolve_database_url(settings.DATABASE_URL)

# SQLite needs check_same_thread=False for multi-threaded FastAPI
_ensure_sqlite_directory(RESOLVED_DATABASE_URL)
connect_args = {"check_same_thread": False} if RESOLVED_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(RESOLVED_DATABASE_URL, echo=False, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _apply_sqlite_schema_updates(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return

    sqlite_path = database_url.replace("sqlite:///", "", 1)
    if sqlite_path == ":memory:":
        return

    db_file = Path(sqlite_path)
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    if not db_file.exists():
        return

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(teams)")
        columns = {row[1] for row in cursor.fetchall()}
        if "location" not in columns:
            cursor.execute("ALTER TABLE teams ADD COLUMN location VARCHAR")
        if "location_place_id" not in columns:
            cursor.execute("ALTER TABLE teams ADD COLUMN location_place_id VARCHAR")
        if "location_lat" not in columns:
            cursor.execute("ALTER TABLE teams ADD COLUMN location_lat REAL")
        if "location_lng" not in columns:
            cursor.execute("ALTER TABLE teams ADD COLUMN location_lng REAL")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS team_decision_contexts (
                id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL UNIQUE,
                schema_version TEXT NOT NULL DEFAULT 'v1',
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_team_decision_contexts_team_id
            ON team_decision_contexts(team_id)
            """
        )
        conn.commit()


def create_db_and_tables() -> None:
    from . import models  # ensure models are imported for metadata

    SQLModel.metadata.create_all(engine)
    _apply_sqlite_schema_updates(RESOLVED_DATABASE_URL)
