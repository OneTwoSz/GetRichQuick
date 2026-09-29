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
    add_missing_columns(engine)


def add_missing_columns(bind) -> list:
    """Additive schema sync for existing databases.

    create_all() creates new tables but never alters existing ones, so a
    column added to a model is missing from databases created before it.
    This adds such columns (nullable, no default) with ALTER TABLE. It never
    drops or changes anything — real migrations are still needed for that.
    Returns the "table.column" names it added.
    """
    from sqlalchemy import inspect
    from sqlalchemy.schema import CreateColumn

    added = []
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present or not column.nullable:
                    continue
                ddl = CreateColumn(column).compile(dialect=bind.dialect)
                conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {ddl}")
                added.append(f"{table.name}.{column.name}")
    return added
