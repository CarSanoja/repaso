from fastapi import FastAPI

from repaso.api import health, judge, memory, webhook
from repaso.api.dependencies import AppContainer

APP_TITLE = "repaso"
APP_VERSION = "0.1.0"


def create_app(container: AppContainer) -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.state.container = container
    app.include_router(health.router)
    app.include_router(webhook.router)
    app.include_router(judge.router)
    app.include_router(memory.router)
    return app
