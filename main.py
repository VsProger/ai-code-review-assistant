from fastapi import FastAPI

from api.routers.webhook import router as webhook_router
from core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="AI Code Review Assistant",
    version="0.2.0",
)

app.include_router(webhook_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
