import os
import sqlite3
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://putka:putka@localhost:5432/putka"
)


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # Używane w testach: jedna współdzielona baza w pamięci.
        sqlite_engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(sqlite_engine, "connect")
        def _enable_foreign_keys(
            dbapi_connection: sqlite3.Connection,
            _connection_record: ConnectionPoolEntry,
        ) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return sqlite_engine
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
