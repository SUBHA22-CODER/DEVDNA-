"""SQLAlchemy engine and session helpers (SQLite for local development)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def init_engine(url: str | None = None):
    """(Re)create the engine. Tests call this with a temporary database URL."""
    global engine
    url = url or settings.resolved_database_url
    if url.startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url)
    SessionLocal.configure(bind=engine)
    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
