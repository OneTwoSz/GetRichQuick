import json

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
from .utils.hashing import _default as _json_default

# SQLite needs `check_same_thread=False` so FastAPI's threadpool can share
# the connection. Postgres/MySQL drivers don't accept that arg, so it's
# applied conditionally. SQLite is the recommended dev default — it lets a
# new contributor run the whole stack without installing Postgres or Docker.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}


def json_serializer(obj) -> str:
    """Serializer for JSON columns (audit log old/new values, Merkle proofs).

    Uses the same datetime/enum normalization as utils.hashing.canonical_json
    so a value read back from the DB re-hashes to the same digest that was
    computed over the original Python objects — verify_chain depends on this.
    """
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    json_serializer=json_serializer,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    from . import models  # Import models to register them
    Base.metadata.create_all(bind=engine)
