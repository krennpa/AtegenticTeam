from pathlib import Path
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from ..core.config import settings


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


# SQLite needs check_same_thread=False for multi-threaded FastAPI
_ensure_sqlite_directory(settings.DATABASE_URL)
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    from . import models  # ensure models are imported for metadata

    SQLModel.metadata.create_all(engine)
