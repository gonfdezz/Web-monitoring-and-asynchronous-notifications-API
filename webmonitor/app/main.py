from contextlib import asynccontextmanager

from app import models  # noqa: F401  -> registra las tablas en SQLModel.metadata
from app.database import init_db
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # aquí irá el apagado del scheduler


app = FastAPI(title="WebMonitor API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}