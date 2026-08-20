import os
import time

from fastapi import FastAPI, Request

from app.auth import hash_password
from app.db import Base, engine, SessionLocal
from app.logger import logger
from app.models import User
from app.monitor import track_request
from app.routes import router

app = FastAPI(
    title="Hospital Appointment System",
    description="Appointment booking with JWT authentication and role-based access.",
    version="1.1.0",
)

Base.metadata.create_all(bind=engine)


def ensure_first_admin():
    """Create a starting administrator when the database has no users at all.

    Public registration deliberately only creates patients, and creating a
    doctor or an administrator requires an administrator - so a brand new
    database would otherwise have no way to get its first one.
    """
    db = SessionLocal()
    try:
        if db.query(User).first():
            return

        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin12345")

        db.add(User(
            username=username,
            email=os.environ.get("ADMIN_EMAIL", "admin@hospital.local"),
            password=hash_password(password),
            role="admin",
        ))
        db.commit()

        logger.warning(
            "Empty database - created the first administrator '%s' with password '%s'. "
            "Change it, or set ADMIN_USERNAME and ADMIN_PASSWORD before first start.",
            username, password,
        )
    finally:
        db.close()


ensure_first_admin()


@app.middleware("http")
async def monitor_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        track_request(start, 500, request.url.path)
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        raise

    route = request.scope.get("route")
    track_request(start, response.status_code, route.path if route else request.url.path)

    logger.info(
        "%s %s -> %s in %.3fs",
        request.method, request.url.path, response.status_code, time.time() - start,
    )
    return response


app.include_router(router)
