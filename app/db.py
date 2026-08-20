from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Anchor the database to the project folder, not to whatever directory the
# server happens to be started from. Without this, running uvicorn from
# elsewhere silently creates a second, empty hospital.db.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "hospital.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    """SQLite ignores foreign keys unless they are switched on per connection."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
