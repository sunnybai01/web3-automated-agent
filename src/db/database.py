from sqlalchemy import create_engine, exc as sa_exc
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables and indexes if they don't exist. Safe for repeated calls."""
    # Import models here to ensure they're registered on Base.metadata before create_all.
    # This avoids circular import issues (models.py imports Base from this module).
    import src.db.models as _models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables and indexes created successfully.")
    except sa_exc.ProgrammingError as e:
        err_msg = str(e.orig) if e.orig else str(e)
        if "already exists" in err_msg:
            logger.debug(f"Skipping duplicate DDL: {e}")
        else:
            raise
