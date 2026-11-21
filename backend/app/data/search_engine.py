"""Catalog search and provider registry for the future EarthTrend Search engine.

This first layer searches metadata, not remote raster/series data. It is deliberately
provider-neutral so direct NASA endpoints can be added beside Earth Engine without
changing the analysis pipeline.
"""
import re
import unicodedata


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[_-]", " ", text.lower()).split())


PROVIDERS = [
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
        if not terms or not all(term in haystack for term in terms):
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


def engine_status():
    return {"name": "EarthTrend Search", "phase": "catalog_search",
            "message": "Esta versão pesquisa metadados do catálogo local; ainda não substitui o acesso aos dados Earth Engine.",
            "providers": PROVIDERS}
