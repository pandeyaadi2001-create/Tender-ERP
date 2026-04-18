"""SQLAlchemy engine, session factory, and schema bootstrap.

The desktop build uses plain SQLite via SQLAlchemy. For production
hardening the spec calls for SQLCipher — swap the URL in
``build_engine`` to ``sqlite+pysqlcipher://...`` once the SQLCipher
Python bindings are available. Everything else in the app already
routes through ``SessionLocal`` so the switch is a one-line change.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DB_PATH, ensure_dirs

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def build_engine(db_path: Optional[Path] = None) -> Engine:
    """Create a SQLite engine with FK enforcement enabled."""
    ensure_dirs()
    path = Path(db_path) if db_path else DB_PATH
    url = f"sqlite:///{path}"
    engine = create_engine(url, future=True, echo=False)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def init_db(db_path: Optional[Path] = None) -> Engine:
    """Initialize (or reinitialize) the global engine and create tables."""
    global _engine, _SessionLocal
    _engine = build_engine(db_path)
    # Import models so Base.metadata is populated before create_all.
    from . import models  # noqa: F401
    from .models.base import Base

    Base.metadata.create_all(_engine)
    # Apply column-level migrations for existing databases
    from .migrate import run_migrations
    run_migrations(_engine)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        init_db()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker:
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager that commits on success, rolls back on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
