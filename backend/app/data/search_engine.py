"""Catalog search and provider registry for the future EarthTrend Search engine.

This first layer searches metadata, not remote raster/series data. It is deliberately
provider-neutral so direct NASA endpoints can be added beside Earth Engine without
changing the analysis pipeline.
"""
import json
import re
import threading
import time
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path

import requests


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[_-]", " ", text.lower()).split())


PROVIDERS = [
    {"id": "copernicus_stac", "name": "Copernicus Data Space STAC", "kind": "live_catalog_discovery", "status": "active",
     "role": "Live search of collection and Angola-intersecting item metadata; product download and raster analysis are separate integrations."},
    {"id": "earth_engine", "name": "Google Earth Engine", "kind": "catalog_and_data", "status": "active",
     "role": "Current provider for configured analysis and raster preview products."},
    {"id": "nasa_earthdata_cmr", "name": "NASA Earthdata CMR", "kind": "live_catalog_discovery", "status": "active",
     "role": "Live NASA collection and granule metadata search using CMR; data download/authentication are separate."},
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


COPERNICUS_STAC_ROOT = "https://stac.dataspace.copernicus.eu/v1"
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



_ITEMS_CACHE = {}
_ITEMS_CACHE_LOCK = threading.Lock()
_ITEMS_CACHE_TTL_SECONDS = 180
_ANGOLA_OUTLINE_PATH = Path(__file__).resolve().parents[2] / "data" / "regions" / "angola-national-outline.geojson"


@lru_cache(maxsize=1)
def _angola_intersects_geometry():
    """Load the dissolved national outline used by the offline map."""
    try:
        payload = json.loads(_ANGOLA_OUTLINE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogProviderError("O contorno nacional de Angola não está disponível para filtrar produtos.") from exc

    polygons = []
    for feature in payload.get("features", []):
        geometry = (feature or {}).get("geometry") or {}
        if geometry.get("type") == "Polygon":
            polygons.append(geometry.get("coordinates") or [])
        elif geometry.get("type") == "MultiPolygon":
            polygons.extend(geometry.get("coordinates") or [])

    polygons = [polygon for polygon in polygons if polygon and polygon[0]]
    if not polygons:
        raise CatalogProviderError("A geometria nacional de Angola está vazia ou num formato inválido.")
    return {"type": "MultiPolygon", "coordinates": polygons}


def _item_summary(feature, collection_id):
    properties = feature.get("properties") or {}
    links = feature.get("links") or []
    self_link = next((link.get("href") for link in links
                      if isinstance(link, dict) and link.get("rel") == "self" and link.get("href")), None)
    item_id = str(feature.get("id") or "")
    item_url = self_link or f"{COPERNICUS_STAC_ROOT}/collections/{collection_id}/items/{item_id}"
    cloud_cover = properties.get("eo:cloud_cover")
    gsd = properties.get("gsd")
    return {
        "id": item_id,
        "collection": str(feature.get("collection") or collection_id),
        "datetime": properties.get("datetime") or properties.get("start_datetime"),
        "platform": properties.get("platform"),
        "instruments": [str(value) for value in (properties.get("instruments") or [])[:5]],
        "cloud_cover": float(cloud_cover) if isinstance(cloud_cover, (int, float)) else None,
        "gsd_m": float(gsd) if isinstance(gsd, (int, float)) else None,
        "processing_level": properties.get("processing:level"),
        "product_type": properties.get("product:type"),
        "bbox": feature.get("bbox"),
        "item_url": item_url,
        "source": "Copernicus Data Space Ecosystem — STAC",
        "catalog_status": "live_metadata",
    }


def search_copernicus_items(collection_id, start_date, end_date, limit=10, max_cloud_cover=None):
    """Search STAC products intersecting the dissolved national outline of Angola."""
    clean_collection = str(collection_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", clean_collection):
        raise ValueError("Indica um identificador de coleção STAC válido.")

    try:
        start = date.fromisoformat(str(start_date))
        end = date.fromisoformat(str(end_date))
    except (TypeError, ValueError) as exc:
        raise ValueError("As datas devem estar no formato AAAA-MM-DD.") from exc
    if end < start:
        raise ValueError("A data final não pode ser anterior à data inicial.")
    if (end - start).days > 366:
        raise ValueError("Cada pesquisa pode abranger no máximo 366 dias.")

    if max_cloud_cover is not None:
        try:
            max_cloud_cover = float(max_cloud_cover)
        except (TypeError, ValueError) as exc:
            raise ValueError("A cobertura máxima de nuvens deve ser um número entre 0 e 100.") from exc
        if not 0 <= max_cloud_cover <= 100:
            raise ValueError("A cobertura máxima de nuvens deve estar entre 0 e 100.")

    safe_limit = max(1, min(int(limit), 20))
    cache_key = (clean_collection.lower(), start.isoformat(), end.isoformat(), safe_limit, max_cloud_cover)
    now = time.monotonic()
    with _ITEMS_CACHE_LOCK:
        cached = _ITEMS_CACHE.get(cache_key)
        if cached and now - cached[0] < _ITEMS_CACHE_TTL_SECONDS:
            return cached[1]

    body = {
        "collections": [clean_collection],
        "intersects": _angola_intersects_geometry(),
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": safe_limit,
    }
    if max_cloud_cover is not None:
        body["filter"] = {
            "op": "lte",
            "args": [{"property": "eo:cloud_cover"}, max_cloud_cover],
        }
        body["filter-lang"] = "cql2-json"
    try:
        response = requests.post(
            f"{COPERNICUS_STAC_ROOT}/search",
            json=body,
            headers={"Accept": "application/geo+json", "Content-Type": "application/json"},
            timeout=(3.05, 20),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CatalogProviderError("A pesquisa de produtos Copernicus não respondeu correctamente. Verifica a coleção e tenta novamente.") from exc

    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise CatalogProviderError("O Copernicus devolveu resultados num formato STAC inesperado.")

    items = [_item_summary(item, clean_collection) for item in features if isinstance(item, dict) and item.get("id")]
    result = {
        "collection": clean_collection,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_cloud_cover": max_cloud_cover,
        "count": len(items),
        "items": items,
        "has_more": any(isinstance(link, dict) and link.get("rel") == "next" for link in (payload.get("links") or [])),
        "source": "Copernicus Data Space Ecosystem STAC API",
        "spatial_scope": "Intersecção com o contorno nacional dissolvido de Angola, baseado na camada geoBoundaries ADM1 de 2021; não contém fronteiras provinciais actuais.",
        "retrieval": "metadata_only",
        "notice": "Estes são registos de produtos que intersectam o contorno nacional de referência. As bandas e ficheiros não foram descarregados nem analisados; o acesso aos assets depende das condições do Copernicus.",
    }
    with _ITEMS_CACHE_LOCK:
        _ITEMS_CACHE[cache_key] = (now, result)
        if len(_ITEMS_CACHE) > 64:
            oldest = min(_ITEMS_CACHE, key=lambda key: _ITEMS_CACHE[key][0])
            _ITEMS_CACHE.pop(oldest, None)
    return result



NASA_CMR_ROOT = "https://cmr.earthdata.nasa.gov/search"
_NASA_CMR_CACHE = {}
_NASA_CMR_CACHE_LOCK = threading.Lock()
_NASA_CMR_CACHE_TTL_SECONDS = 180


def _cache_read(key):
    now = time.monotonic()
    with _NASA_CMR_CACHE_LOCK:
        cached = _NASA_CMR_CACHE.get(key)
        if cached and now - cached[0] < _NASA_CMR_CACHE_TTL_SECONDS:
            return cached[1]
    return None


def _cache_write(key, value):
    with _NASA_CMR_CACHE_LOCK:
        _NASA_CMR_CACHE[key] = (time.monotonic(), value)
        if len(_NASA_CMR_CACHE) > 64:
            oldest = min(_NASA_CMR_CACHE, key=lambda k: _NASA_CMR_CACHE[k][0])
            _NASA_CMR_CACHE.pop(oldest, None)


def _cmr_collection_summary(entry):
    links = entry.get("links") or []
    metadata_url = next((link.get("href") for link in links
                         if isinstance(link, dict) and (str(link.get("rel", "")).lower() == "metadata" or str(link.get("rel", "")).lower().endswith("metadata#"))), None)
    concept_id = entry.get("id")
    temporal = entry.get("time_start") or entry.get("temporal")
    return {
        "id": concept_id,
        "short_name": entry.get("short_name"),
        "title": entry.get("title") or entry.get("dataset_id") or entry.get("short_name"),
        "version": entry.get("version"),
        "provider": entry.get("provider"),
        "summary": entry.get("摘要") or entry.get("summary") or entry.get("description") or "",
        "start_date": entry.get("time_start"),
        "end_date": entry.get("time_end"),
        "bbox": entry.get("boxes") or entry.get("bounding_boxes"),
        "metadata_url": metadata_url or (f"https://cmr.earthdata.nasa.gov/search/concepts/{concept_id}" if concept_id else None),
        "earthdata_url": f"https://search.earthdata.nasa.gov/search?q={requests.utils.quote(str(entry.get('short_name') or entry.get('title') or ''))}",
        "source": "NASA Earthdata Common Metadata Repository (CMR)",
        "catalog_status": "live_metadata",
    }


def search_nasa_cmr_collections(query="", limit=10):
    """Live CMR collection discovery. Search metadata only; no granules are downloaded."""
    clean_query = str(query or "").strip()[:120]
    safe_limit = max(1, min(int(limit), 20))
    key = ("collections", clean_query.lower(), safe_limit)
    cached = _cache_read(key)
    if cached is not None:
        return cached
    params = {"page_size": safe_limit, "sort_key": "-score", "include_facets": "false"}
    if clean_query:
        params["keyword"] = clean_query
    try:
        response = requests.get(f"{NASA_CMR_ROOT}/collections.json", params=params,
                               headers={"Accept": "application/json"}, timeout=(3.05, 20))
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CatalogProviderError("A pesquisa NASA Earthdata CMR não respondeu correctamente. Tenta novamente.") from exc
    entries = ((payload.get("feed") or {}).get("entry") or []) if isinstance(payload, dict) else []
    results = [_cmr_collection_summary(entry) for entry in entries if isinstance(entry, dict)]
    hits = response.headers.get("CMR-Hits")
    result = {
        "query": clean_query,
        "count": len(results),
        "total_hits": int(hits) if hits and hits.isdigit() else None,
        "results": results,
        "source": "NASA Earthdata CMR",
        "catalogue_url": "https://cmr.earthdata.nasa.gov/search/collections",
        "retrieval": "metadata_only",
        "notice": "Pesquisa de coleções e metadados CMR. A disponibilidade de granules, ficheiros e acesso pode variar por produto e autenticação.",
    }
    _cache_write(key, result)
    return result


def search_nasa_cmr_granules(short_name, start_date, end_date, limit=10, max_cloud_cover=None):
    """Live granule metadata search within an Angola bounding box, optionally cloud-filtered."""
    clean_short_name = str(short_name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", clean_short_name):
        raise ValueError("Indica um short name NASA válido.")
    try:
        start = date.fromisoformat(str(start_date))
        end = date.fromisoformat(str(end_date))
    except (TypeError, ValueError) as exc:
        raise ValueError("As datas devem estar no formato AAAA-MM-DD.") from exc
    if end < start:
        raise ValueError("A data final não pode ser anterior à inicial.")
    if (end - start).days > 366:
        raise ValueError("Cada pesquisa pode abranger no máximo 366 dias.")
    if max_cloud_cover is not None:
        try:
            max_cloud_cover = float(max_cloud_cover)
        except (TypeError, ValueError) as exc:
            raise ValueError("A cobertura máxima de nuvens deve ser um número entre 0 e 100.") from exc
        if not 0 <= max_cloud_cover <= 100:
            raise ValueError("A cobertura máxima de nuvens deve estar entre 0 e 100.")
    safe_limit = max(1, min(int(limit), 20))
    key = ("granules", clean_short_name.lower(), start.isoformat(), end.isoformat(), safe_limit, max_cloud_cover)
    cached = _cache_read(key)
    if cached is not None:
        return cached
    params = {
        "short_name": clean_short_name,
        "temporal": f"{start.isoformat()}T00:00:00Z,{end.isoformat()}T23:59:59Z",
        "bounding_box": "11.6,-18.1,24.1,-4.2",
        "page_size": safe_limit,
        "sort_key": "-start_date",
    }
    if max_cloud_cover is not None:
        params["cloud_cover"] = f",{max_cloud_cover}"
    try:
        response = requests.get(f"{NASA_CMR_ROOT}/granules.json", params=params,
                               headers={"Accept": "application/json"}, timeout=(3.05, 20))
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CatalogProviderError("A pesquisa NASA CMR de granules não respondeu correctamente. Confirma o short name e tenta novamente.") from exc
    entries = ((payload.get("feed") or {}).get("entry") or []) if isinstance(payload, dict) else []
    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        links = entry.get("links") or []
        data_links = [link.get("href") for link in links if isinstance(link, dict)
                      and link.get("rel") in ("data", "http://esipfed.org/ns/fedsearch/1.1/data#")]
        browse_links = [link.get("href") for link in links if isinstance(link, dict)
                        and link.get("rel") in ("browse", "http://esipfed.org/ns/fedsearch/1.1/browse#")]
        items.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "producer_granule_id": entry.get("producer_granule_id"),
            "short_name": entry.get("short_name") or clean_short_name,
            "collection_concept_id": entry.get("collection_concept_id"),
            "start_date": entry.get("time_start"),
            "end_date": entry.get("time_end"),
            "cloud_cover": float(entry["cloud_cover"]) if entry.get("cloud_cover") not in (None, "") else None,
            "day_night": entry.get("day_night_flag"),
            "size_mb": float(entry.get("granule_size") or entry.get("size")) if entry.get("granule_size") not in (None, "") or entry.get("size") not in (None, "") else None,
            "data_links": data_links[:3],
            "browse_links": browse_links[:2],
            "metadata_url": f"https://cmr.earthdata.nasa.gov/search/concepts/{entry.get('id')}" if entry.get("id") else None,
            "source": "NASA Earthdata CMR",
            "catalog_status": "live_metadata",
        })
    hits = response.headers.get("CMR-Hits")
    result = {
        "short_name": clean_short_name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_cloud_cover": max_cloud_cover,
        "count": len(items),
        "total_hits": int(hits) if hits and hits.isdigit() else None,
        "items": items,
        "source": "NASA Earthdata Common Metadata Repository (CMR)",
        "spatial_scope": "Bounding box aproximada de Angola (11.6°E–24.1°E, 18.1°S–4.2°S); pode incluir áreas vizinhas, não é uma intersecção com a fronteira nacional.",
        "retrieval": "metadata_only",
        "notice": "Os resultados são metadados de granules. Os ficheiros não foram descarregados nem analisados; links de dados podem requerer Earthdata Login ou permissões específicas.",
    }
    _cache_write(key, result)
    return result

def engine_status():
    return {"name": "EarthTrend Search", "phase": "catalog_search", "phase_detail": "multi_source_catalog_search",
            "message": "Pesquisa catálogo interno, coleções e granules NASA CMR, coleções e produtos Copernicus; a descarga e análise raster de produtos externos ainda são integrações separadas.",
            "providers": PROVIDERS}
