"""Endpoints da API. Só traduzem HTTP para chamadas ao Service e de volta."""
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from ..security import enforce_rate_limit
from ..errors import ApiError
from ..data.search_engine import CatalogProviderError, search_catalog, search_copernicus_collections, search_copernicus_items, search_nasa_cmr_collections, search_nasa_cmr_granules, engine_status

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


@router.get("/ml/status", tags=["aprendizagem"], summary="Estado dos modelos de aprendizagem adaptativa")
def ml_status(request: Request):
    return _svc(request).learning_status()


@router.get("/datasets", tags=["dados"], summary="Datasets registados e se já têm dados no servidor")
def datasets(request: Request):
    return {"datasets": _svc(request).list_datasets()}


@router.get("/search/status", tags=["pesquisa"], summary="Estado do motor EarthTrend Search")
def search_status():
    return engine_status()


@router.get("/search/catalog", tags=["pesquisa"], summary="Pesquisa local no catálogo de dados")
def search_catalog_endpoint(request: Request, q: str = Query("", max_length=120), limit: int = Query(20, ge=1, le=50)):
    enforce_rate_limit(request, "catalog_search", limit=60, window_seconds=60)
    datasets = _svc(request).list_datasets()
    matches = search_catalog(datasets, q, limit)
    return {"query": q, "count": len(matches), "results": matches, "engine": engine_status()}


@router.get("/search/copernicus/collections", tags=["pesquisa"], summary="Pesquisa ao vivo de coleções Copernicus STAC")
def copernicus_collections_endpoint(
    request: Request,
    q: str = Query("", max_length=120),
    limit: int = Query(10, ge=1, le=20),
):
    enforce_rate_limit(request, "copernicus_catalog", limit=20, window_seconds=60)
    try:
        return search_copernicus_collections(q, limit)
    except CatalogProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/search/copernicus/items", tags=["pesquisa"], summary="Pesquisa produtos Copernicus que intersectam Angola")
def copernicus_items_endpoint(
    request: Request,
    collection: str = Query("sentinel-2-l2a", min_length=1, max_length=120),
    start: str = Query(..., min_length=10, max_length=10),
    end: str = Query(..., min_length=10, max_length=10),
    limit: int = Query(10, ge=1, le=20),
    max_cloud_cover: float | None = Query(None, ge=0, le=100),
):
    enforce_rate_limit(request, "copernicus_items", limit=12, window_seconds=60)
    try:
        return search_copernicus_items(collection, start, end, limit, max_cloud_cover)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CatalogProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/search/nasa/cmr/collections", tags=["pesquisa"], summary="Pesquisa ao vivo de coleções NASA Earthdata CMR")
def nasa_cmr_collections_endpoint(
    request: Request,
    q: str = Query("", max_length=120),
    limit: int = Query(10, ge=1, le=20),
):
    enforce_rate_limit(request, "nasa_cmr_catalog", limit=20, window_seconds=60)
    try:
        return search_nasa_cmr_collections(q, limit)
    except CatalogProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/search/nasa/cmr/granules", tags=["pesquisa"], summary="Pesquisa granules NASA CMR sobre a região aproximada de Angola")
def nasa_cmr_granules_endpoint(
    request: Request,
    short_name: str = Query(..., min_length=1, max_length=120),
    start: str = Query(..., min_length=10, max_length=10),
    end: str = Query(..., min_length=10, max_length=10),
    limit: int = Query(10, ge=1, le=20),
    max_cloud_cover: float | None = Query(None, ge=0, le=100),
):
    enforce_rate_limit(request, "nasa_cmr_granules", limit=12, window_seconds=60)
    try:
        return search_nasa_cmr_granules(short_name, start, end, limit, max_cloud_cover)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CatalogProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/regions", tags=["dados"], summary="Regiões disponíveis e o tipo de fronteira de cada uma")
def regions(request: Request):
    return {"regions": _svc(request).list_regions()}


@router.get("/regions/{region_id}/geojson", tags=["mapas"], summary="Geometria local para mapa-base")
def region_geojson(region_id: str, request: Request):
    registry = _svc(request).registry
    entry = registry._entry(region_id)
    path = registry._boundary_path(entry["id"])
    if not path.is_file():
        raise ApiError(404, "boundary_not_found", "A geometria desta região não está disponível localmente.")
    import json
    with open(path, encoding="utf-8") as fh:
        geometry = json.load(fh)
    return Response(content=json.dumps(geometry, ensure_ascii=False), media_type="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/maps/preview", tags=["mapas"], summary="Raster temporal real do Google Earth Engine")
def map_preview(request: Request,
                dataset_id: str = Query(..., min_length=1, max_length=64),
                region_id: str = Query(..., min_length=1, max_length=64),
                start: str = Query(..., min_length=4, max_length=10),
                end: str = Query(..., min_length=4, max_length=10)):
    enforce_rate_limit(request, "map_preview", limit=30, window_seconds=60)
    image, dataset, region = _svc(request).map_preview({
        "dataset_id": dataset_id, "region_id": region_id, "start": start, "end": end,
    })
    return Response(
        content=image,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-EarthTrend-Map-Source": "Google Earth Engine",
            "X-EarthTrend-Dataset": dataset.get("id", ""),
            "X-EarthTrend-Region": region.get("name", ""),
            "X-EarthTrend-Statistic": "Média temporal das imagens disponíveis no período",
        },
    )


@router.post("/analyze", tags=["análise"], summary="Executa uma análise de tendência e guarda o resultado")
def analyze(body: AnalysisRequest, request: Request):
    enforce_rate_limit(request, "analyze", limit=10, window_seconds=600)
    return _svc(request).analyze(body.model_dump())


@router.get("/results", tags=["análise"], summary="Listagem desactivada por privacidade")
def results():
    raise ApiError(404, "results_listing_disabled",
                   "A listagem pública de análises foi desactivada. Abra um resultado através do seu link privado.")


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
