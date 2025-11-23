from fastapi import FastAPI
from api.routers.webhook import router as webhook_router

app = FastAPI(
    title="AI Code Review Assistant",
    version="0.1.0",
)

# Подключаем роутер с вебхуком
app.include_router(webhook_router)
