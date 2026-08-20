"""A brand new database has to be able to produce its first administrator."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import User


def test_first_admin_is_created_when_the_database_is_empty(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    import app.main as main
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setenv("ADMIN_USERNAME", "rootadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "rootpass123")

    main.ensure_first_admin()

    db = Session()
    admin = db.query(User).filter(User.username == "rootadmin").first()
    assert admin is not None
    assert admin.role == "admin"

    from app.auth import verify_password
    assert verify_password("rootpass123", admin.password)
    db.close()


def test_bootstrap_does_nothing_when_users_exist(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'used.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    db.add(User(username="someone", email="s@t.com", password="x", role="patient"))
    db.commit()
    db.close()

    import app.main as main
    monkeypatch.setattr(main, "SessionLocal", Session)
    main.ensure_first_admin()

    db = Session()
    assert db.query(User).count() == 1
    db.close()
