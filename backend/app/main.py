"""Ponto de entrada. Em desenvolvimento, a partir de backend/:  uvicorn app.main:app --reload"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api.routes import router
from .config import Settings
from .data.registry import Registry
from .data.earth_engine import EarthEngineLoader
from .errors import ApiError
from .service import Service
from .storage import ResultStore

log = logging.getLogger("earthtrend")

DESCRIPTION = (
    "Deteção de tendências ambientais com dados NASA. Cada resultado traz a direção, a magnitude (declive de Sen "
    "com intervalo de confiança), a significância (Mann-Kendall), a proveniência dos dados e as limitações. "
    "Nada é preenchido à mão: sem dados no servidor a resposta é um erro claro, nunca números inventados."
)


def create_app(settings=None, loader=None):
    settings = settings or Settings.from_env()
    app = FastAPI(title="EarthTrend AI API", version=__version__, description=DESCRIPTION)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    registry = Registry.load(settings.config_dir, settings.regions_dir)
    data_loader = loader or EarthEngineLoader(
        settings.raw_dir, settings.regions_dir,
        project_id=settings.ee_project_id,
        service_account_json=settings.ee_service_account_json,
    )
    app.state.service = Service(settings, registry, data_loader, ResultStore(settings.results_dir))

    @app.exception_handler(ApiError)
    async def api_error_handler(request, exc):
        return JSONResponse(status_code=exc.status, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request, exc):
        log.exception("Erro inesperado em %s", request.url.path)
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "Erro interno ao processar o pedido.", "details": {}}})

    app.include_router(router)
    return app


app = create_app()
