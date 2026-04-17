from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from ..core.config import settings

# SQLite needs check_same_thread=False for multi-threaded FastAPI
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    from . import models  # ensure models are imported for metadata

    SQLModel.metadata.create_all(engine)
