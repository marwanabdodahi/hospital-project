from fastapi import FastAPI, Request
import time

from app.db import Base, engine
from app.routes import router
from app import models
from app.monitor import track_request  

app = FastAPI()

Base.metadata.create_all(bind=engine)

@app.middleware("http")
async def monitor_middleware(request: Request, call_next):
    start = time.time()

    try:
        response = await call_next(request)
        track_request(start, success=True)
        return response
    except Exception:
        track_request(start, success=False)
        raise

app.include_router(router)