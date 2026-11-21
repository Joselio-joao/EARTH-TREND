"""Catalog search and provider registry for the future EarthTrend Search engine.

This first layer searches metadata, not remote raster/series data. It is deliberately
provider-neutral so direct NASA endpoints can be added beside Earth Engine without
changing the analysis pipeline.
"""
import re
import threading
import time
import unicodedata

import requests


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[_-]", " ", text.lower()).split())


PROVIDERS = [
    {"id": "copernicus_stac", "name": "Copernicus Data Space STAC", "kind": "live_catalog_discovery", "status": "active",
     "role": "Live search of collection metadata; direct product download and analysis are separate integrations."},
    {"id": "earth_engine", "name": "Google Earth Engine", "kind": "catalog_and_data", "status": "active",
     "role": "Current provider for configured analysis and raster preview products."},
    {"id": "nasa_earthdata", "name": "NASA Earthdata / CMR", "kind": "catalog_discovery", "status": "planned",
     "role": "Independent discovery of NASA collections and granules; access/authentication varies by product."},
    {"id": "ges_disc", "name": "NASA GES DISC", "kind": "data_provider", "status": "planned",
     "role": "Direct access paths for hydrology and atmospheric products, subject to product access rules."},
    {"id": "lp_daac", "name": "NASA LP DAAC", "kind": "data_provider", "status": "planned",
     "role": "Direct land-product access, including vegetation and land-surface products."},
    {"id": "podaac", "name": "NASA PO.DAAC", "kind": "data_provider", "status": "planned",
     "role": "Ocean and surface-water product discovery and retrieval."},
]


def search_catalog(datasets, query, limit=20):
    """Rank local dataset metadata matches. Never imply that planned items are query-ready."""
    q = normalize(query)
    terms = [term for term in q.split() if term]
    results = []
    for dataset in datasets:
        haystack = normalize(" ".join(str(dataset.get(k, "")) for k in (
            "id", "name", "family", "variable_id", "variable_label", "provider",
            "product_short_name", "coverage_note", "note", "product_url", "doi"
        )))
        if terms and not all(term in haystack for term in terms):
            continue
        score = sum(3 if term in normalize(dataset.get("variable_label", "")) else
                    2 if term in normalize(dataset.get("name", "")) else 1 for term in terms)
        results.append({"dataset": dataset, "score": score})
    results.sort(key=lambda item: (-item["score"], item["dataset"].get("status") != "available",
                                   item["dataset"].get("name", "")))
    return [{"id": d["id"], "name": d.get("name"), "variable_label": d.get("variable_label"),
             "provider": d.get("provider"), "status": d.get("status"),
             "coverage_start": d.get("coverage_start"), "coverage_end": d.get("coverage_end"),
             "display_unit": d.get("display_unit") or d.get("native_unit"),
             "source_cadence": d.get("source_cadence"), "spatial_resolution_m": d.get("spatial_resolution_m"),
             "product_url": d.get("product_url"), "note": d.get("note"),
             "limitations": d.get("limitations", [])} for item in results[:max(1, min(int(limit), 50))]
             for d in [item["dataset"]]]


COPERNICUS_STAC_ROOT = "https://stac.opensearch.dataspace.copernicus.eu/v1"
_COLLECTIONS_CACHE = {}
_COLLECTIONS_CACHE_LOCK = threading.Lock()
_COLLECTIONS_CACHE_TTL_SECONDS = 300


class CatalogProviderError(RuntimeError):
    """Remote catalogue failed or returned an invalid response."""


def _collection_summary(collection):
    extent = collection.get("extent") or {}
    spatial = extent.get("spatial") or {}
    temporal = extent.get("temporal") or {}
    intervals = temporal.get("interval") or []
    interval = intervals[0] if intervals and isinstance(intervals[0], list) else [None, None]
    assets = collection.get("assets") or {}
    thumbnail = assets.get("thumbnail") or {}
    providers = collection.get("providers") or []
    bbox = spatial.get("bbox") or []
    return {
        "id": str(collection.get("id") or ""),
        "title": str(collection.get("title") or collection.get("id") or "Coleção sem título"),
        "description": str(collection.get("description") or "")[:700],
        "license": str(collection.get("license") or "Não indicada no registo da coleção"),
        "updated": collection.get("updated"),
        "temporal_start": interval[0] if len(interval) > 0 else None,
        "temporal_end": interval[1] if len(interval) > 1 else None,
        "bbox": bbox[0] if bbox and isinstance(bbox[0], list) else None,
        "keywords": [str(value) for value in (collection.get("keywords") or [])[:12]],
        "providers": [str(item.get("name")) for item in providers if isinstance(item, dict) and item.get("name")][:5],
        "thumbnail_url": thumbnail.get("href") if isinstance(thumbnail, dict) else None,
        "collection_url": f"{COPERNICUS_STAC_ROOT}/collections/{collection.get('id')}",
        "source": "Copernicus Data Space Ecosystem — STAC",
        "catalog_status": "live_metadata",
    }


def search_copernicus_collections(query="", limit=10):
    """Search the live Copernicus STAC collection catalogue; does not download products."""
    clean_query = str(query or "").strip()[:120]
    safe_limit = max(1, min(int(limit), 20))
    cache_key = (normalize(clean_query), safe_limit)
    now = time.monotonic()
    with _COLLECTIONS_CACHE_LOCK:
        cached = _COLLECTIONS_CACHE.get(cache_key)
        if cached and now - cached[0] < _COLLECTIONS_CACHE_TTL_SECONDS:
            return cached[1]

    params = {"limit": safe_limit}
    if clean_query:
        params["q"] = clean_query
    try:
        response = requests.get(
            f"{COPERNICUS_STAC_ROOT}/collections",
            params=params,
            headers={"Accept": "application/json"},
            timeout=(3.05, 12),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CatalogProviderError("O catálogo Copernicus não respondeu correctamente. Tenta novamente mais tarde.") from exc

    collections = payload.get("collections") if isinstance(payload, dict) else None
    if not isinstance(collections, list):
        raise CatalogProviderError("O catálogo Copernicus devolveu uma resposta num formato inesperado.")

    results = [_collection_summary(item) for item in collections if isinstance(item, dict) and item.get("id")]
    result = {
        "query": clean_query,
        "count": len(results),
        "results": results,
        "source": "Copernicus Data Space Ecosystem STAC API",
        "catalogue_url": f"{COPERNICUS_STAC_ROOT}/collections",
        "retrieval": "metadata_only",
        "notice": "A pesquisa descobre coleções. A disponibilidade de ficheiros, autenticação e condições de utilização dependem de cada produto.",
    }
    with _COLLECTIONS_CACHE_LOCK:
        _COLLECTIONS_CACHE[cache_key] = (now, result)
        if len(_COLLECTIONS_CACHE) > 64:
            oldest = min(_COLLECTIONS_CACHE, key=lambda key: _COLLECTIONS_CACHE[key][0])
            _COLLECTIONS_CACHE.pop(oldest, None)
    return result


def engine_status():
    return {"name": "EarthTrend Search", "phase": "catalog_search",
            "message": "Pesquisa o catálogo interno e consulta ao vivo metadados de coleções Copernicus; a descarga e análise de produtos externos ainda são integrações separadas.",
            "providers": PROVIDERS}
