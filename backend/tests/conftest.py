"""
Shared fixtures: an in-memory SQLite database and a TestClient whose auth
dependency is overridden with a seeded factory manager.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, json_serializer
from app.main import app
from app.models import Factory, User, UserRole
from app.utils.auth import get_current_user

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    json_serializer=json_serializer,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()

    user = User(email="mill@example.com", password_hash="x", name="Mill", role=UserRole.FACTORY_MANAGER)
    session.add(user)
    session.flush()
    factory = Factory(user_id=user.id, name="Tiruppur Knits", location="Tiruppur")
    session.add(factory)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)
