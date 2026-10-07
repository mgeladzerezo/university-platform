from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.academics.router import router as academics_router
from app.admissions.router import router as admissions_router
from app.assistant.router import router as assistant_router
from app.config import get_settings
from app.content.router import catalogue_admin, cms, public
from app.db import make_engine, make_session_factory
from app.errors import register_error_handlers
from app.jobs import load_job_modules
from app.metrics import install_metrics
from app.services import Services, build_services

API_PREFIX = "/api/v1"
ROUTERS = (
    public,
    cms,
    catalogue_admin,
    admissions_router,
    academics_router,
    assistant_router,
)


def create_app(services: Services, session_factory: sessionmaker[Session]) -> FastAPI:
    app = FastAPI(title="Kalinowo University API", version="0.1.0")
    app.state.services = services
    app.state.session_factory = session_factory

    load_job_modules()
    register_error_handlers(app)
    install_metrics(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=services.settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    api = APIRouter(prefix=API_PREFIX)
    for router in ROUTERS:
        api.include_router(router)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readiness(request: Request) -> JSONResponse:
        try:
            with request.app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "database unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app


def create_production_app() -> FastAPI:
    settings = get_settings()
    return create_app(
        build_services(settings), make_session_factory(make_engine(settings.database_url))
    )
