import time

from fastapi import FastAPI, Request

from app.db import Base, engine
from app.logger import logger
from app.monitor import track_request
from app.routes import router

app = FastAPI(
    title="Hospital Appointment System",
    description="Appointment booking with JWT authentication and role-based access.",
    version="1.0.0",
)

Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def monitor_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        track_request(start, 500, request.url.path)
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        raise

    track_request(start, response.status_code, request.url.path)
    logger.info(
        "%s %s -> %s in %.3fs",
        request.method, request.url.path, response.status_code, time.time() - start,
    )
    return response


app.include_router(router)
