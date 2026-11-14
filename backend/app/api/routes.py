"""Endpoints da API. Só traduzem HTTP para chamadas ao Service e de volta."""
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from .schemas import AnalysisRequest

router = APIRouter()


def _svc(request: Request):
    return request.app.state.service


@router.get("/", tags=["sistema"], summary="Informação da API")
def root(request: Request):
    return {"name": "EarthTrend AI API", "version": _svc(request).health()["version"], "docs": "/docs"}


@router.get("/health", tags=["sistema"], summary="O backend está ativo?")
def health(request: Request):
    return _svc(request).health()


@router.get("/datasets", tags=["dados"], summary="Datasets registados e se já têm dados no servidor")
def datasets(request: Request):
    return {"datasets": _svc(request).list_datasets()}


@router.get("/regions", tags=["dados"], summary="Regiões disponíveis e o tipo de fronteira de cada uma")
def regions(request: Request):
    return {"regions": _svc(request).list_regions()}


@router.post("/analyze", tags=["análise"], summary="Executa uma análise de tendência e guarda o resultado")
def analyze(body: AnalysisRequest, request: Request):
    return _svc(request).analyze(body.model_dump())


@router.get("/results", tags=["análise"], summary="Últimas análises guardadas")
def results(request: Request, limit: int = Query(20, ge=1, le=100)):
    return {"results": _svc(request).list_results(limit)}


@router.get("/results/{result_id}", tags=["análise"], summary="Resultado completo de uma análise")
def result(result_id: str, request: Request):
    return _svc(request).get_result(result_id)


@router.get("/results/{result_id}/map", tags=["análise"], summary="Grelha do mapa (média no período)")
def result_map(result_id: str, request: Request):
    return _svc(request).get_map(result_id)


@router.get("/results/{result_id}/trend-map", tags=["análise"],
            summary="Mapa de tendência estatística célula a célula")
def result_trend_map(result_id: str, request: Request):
    return _svc(request).get_trend_map(result_id)


@router.get("/results/{result_id}/series.csv", tags=["análise"], summary="Série temporal em CSV")
def result_csv(result_id: str, request: Request):
    text, filename = _svc(request).series_csv(result_id)
    return Response(content=text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename})


@router.get("/report/{result_id}", tags=["relatório"], summary="Relatório (HTML para imprimir, ou Markdown)")
def report(result_id: str, request: Request, format: str = Query("html", description="html ou md")):
    content, media_type = _svc(request).report(result_id, format)
    return Response(content=content, media_type=media_type)
