"""
Database engine and session management.
Uses SQLAlchemy 2.0 synchronous engine with SQLite.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings

# ─── Engine ───
# SQLite requires check_same_thread=False for FastAPI's threaded model
engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

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
