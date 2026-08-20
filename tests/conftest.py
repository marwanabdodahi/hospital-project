import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import redis

from app.auth import hash_password
from app.db import Base
from app.dependencies import get_db
from app.main import app
from app.models import User


@pytest.fixture(autouse=True)
def clear_cache():
    """Cached lists are shared across databases, so start every test with an empty cache."""
    from app.cache import r
    try:
        r.flushdb()
    except redis.RedisError:
        pass  # Redis is optional - nothing to clear when it is not running
    yield


@pytest.fixture()
def db_session(tmp_path):
    """A fresh, empty database for each test."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(client, db_session):
    """Create a user of any role. Returns (auth_headers, user_id)."""
    def _make(username, role="patient", password="secret123"):
        user = User(
            username=username,
            email=f"{username}@test.com",
            password=hash_password(password),
            role=role,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = client.post(
            "/login", json={"username": username, "password": password}
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, user.id

    return _make
