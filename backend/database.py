"""
Database engine and session management.
Uses SQLAlchemy 2.0 synchronous engine with SQLite.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings

# ─── Engine ───
# SQLite requires check_same_thread=False for FastAPI's threaded model.
# WAL journal mode allows concurrent readers + one writer without locking.
# busy_timeout tells SQLite to retry for up to 30s before raising "database is locked".
from sqlalchemy import event

engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False,
)

@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_connection, connection_record):
    try:
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA synchronous=NORMAL")
        dbapi_connection.execute("PRAGMA busy_timeout=30000")
    except Exception:
        # DB may be locked by a running scanner — safe to skip,
        # WAL mode persists once set and busy_timeout applies on next connection.
        pass

# ─── Session factory ───
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── Base class for all ORM models ───
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency that provides a database session.
    Automatically closes the session after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined by ORM models."""
    from models import Artist, Scandal, ScandalSource, ScandalVote, CommunityScandal  # noqa: F401
    Base.metadata.create_all(bind=engine)
