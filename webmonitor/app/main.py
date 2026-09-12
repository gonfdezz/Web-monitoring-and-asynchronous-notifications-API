import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import models  # noqa: F401
from app.database import init_db
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    async with httpx.AsyncClient(limits=limits) as client:
        app.state.http_client = client
        start_scheduler(client)
        yield
        stop_scheduler()


app = FastAPI(title="WebMonitor API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}