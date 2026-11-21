# EarthTrend Search — architecture and migration plan

**Status:** phase 4 in progress (local search + Copernicus collection/items + NASA CMR collection discovery)  
**Current data engine:** Google Earth Engine remains the active provider for products configured in the backend.  
**Goal:** build a source-neutral data discovery and ingestion layer, then add direct NASA providers in parallel.

## Separation of responsibilities

1. **Search index:** searchable metadata (variable, mission, collection/product, provider, units, cadence, coverage, resolution, license/citation, readiness).
2. **Provider adapters:** one adapter per source. An adapter exposes catalog discovery and, where supported, data retrieval; it must report authentication, coverage and errors distinctly.
3. **Normalizer:** converts retrieved series to the internal schema and units, preserves source granularity, quality flags, and timestamps.
4. **Cache:** immutable cache keys include provider, collection/product, region, date range, version and processing options.
5. **Analysis:** trend calculations remain provider-agnostic; only normalized observations reach the existing pipeline.
6. **Map renderer:** source raster/grid where available; local boundary layer always independent from the data provider.

## Provider status

- Google Earth Engine: **active**; existing configured datasets.
- Copernicus Data Space STAC: **active for live collection and Angola-intersecting item metadata discovery**; asset retrieval and raster analysis are not yet integrated.
- NASA Earthdata CMR: **active for live collection metadata discovery**; granule search and direct download remain separate integrations.
- NASA GES DISC: **planned** direct product retrieval, including access checks and formats.
- NASA LP DAAC: **planned** direct land-product retrieval.
- NASA PO.DAAC: **planned** ocean/surface-water discovery and retrieval.
- Giovanni/AppEEARS: **external tools for now**; exports require provenance, unit and quality validation before import.

## Candidate catalogue expansion (do not mark available until connector and tests exist)

| Domain | Candidate variable/product family | Source candidates |
|---|---|---|
| Rainfall | precipitation rate/accumulation | GPM IMERG |
| Vegetation | NDVI, EVI | MODIS / VIIRS |
| Temperature | land surface temperature, air temperature | MODIS LST / GLDAS |
| Soil | surface soil moisture | GLDAS / SMAP |
| Water | surface-water height/extent | SWOT |
| Evaporation | evapotranspiration | MODIS ET / SSEBop where provenance verified |
| Fire | burned area, active fire | MODIS / VIIRS |
| Land cover | land-cover class/change | MODIS MCD12Q1 / Landsat |
| Atmosphere | aerosol optical depth | MODIS / MAIAC |
| Gravity/water storage | terrestrial water-storage anomaly | GRACE / GRACE-FO |

Each catalogue item must have official product citation, version, units, temporal/spatial resolution, coverage, access status, QA rules, limitations and a test case. Catalogue discovery is not equivalent to a product being executable.

## Earth Engine migration gates

Do not remove Earth Engine until a replacement connector demonstrates parity for:
- the existing available dataset list;
- temporal coverage and quality filters;
- validated units and missing-value handling;
- regional aggregation and raster previews;
- analysis reproducibility and cache behavior;
- automated tests and graceful provider outages.

## Phase 2 implemented — Copernicus collection discovery

- Live collection search endpoint: `/search/copernicus/collections?q=...`.
- Uses the current official Copernicus Data Space Ecosystem STAC 1.1 endpoint: `https://stac.dataspace.copernicus.eu/v1`.
- Search covers collection titles, descriptions and keywords via the STAC collection `q` parameter.
- The backend applies a bounded result limit, timeout, per-client rate limit and short in-memory cache.
- Search results preserve the collection ID, title, description, provider, declared license, temporal extent, spatial extent, keywords and official STAC URL.
- UI is available in the Data Library as “Pesquisa ao vivo · Copernicus STAC”.
- Automated tests cover result mapping, cache behavior and remote provider failure.
- This is **catalogue discovery only**. It does not yet download products, fetch raster assets or run Copernicus observations through the trend engine.

## Phase 1 implemented

- Local metadata search endpoint: /search/catalog.
- Provider state endpoint: /search/status.
- Search UI in Data Library.
- Search ranks matching dataset metadata and exposes status, source, coverage, units, resolution and official link.
- It does **not** search remote NASA collections or retrieve data yet.

## Phase 3 implemented — Copernicus item discovery for Angola

- Live item endpoint: `/search/copernicus/items?collection=sentinel-2-l2a&start=2026-10-01&end=2026-10-31&limit=10`, using the current official CDSE STAC endpoint.
- Uses STAC Item Search with the dissolved national outline of Angola as a GeoJSON `intersects` geometry, rather than a broad rectangular bounding box.
- Returns product ID, acquisition time, platform, sensor, declared cloud cover, nominal GSD, processing level, product type and official STAC item URL.
- Maximum date span is 366 days, results are capped, requests are rate-limited and responses are briefly cached.
- Optional maximum cloud-cover filter uses the CDSE STAC CQL2 JSON filter on `eo:cloud_cover` (0–100%).
- The UI appears under the Copernicus panel in the Data Library and allows collection ID/date range selection.
- The spatial filter uses the same dissolved 2021 national outline as the offline map. It does not claim current provincial borders or legal/cadastral precision.
- Results are metadata-only: assets/bands are not downloaded and no Copernicus raster is run through the trend engine.
- Tests cover item mapping, spatial request, time-range validation and response-cache behavior.

## Phase 4 implemented — NASA CMR collection discovery

- Live endpoint: `/search/nasa/cmr/collections?q=GPM%20IMERG&limit=12`.
- Uses the public NASA CMR collection search API with keyword search and JSON response metadata.
- Returns CMR concept ID, collection title, short name, version, provider/DAAC, temporal coverage, declared granule count, cloud-hosted flag and official metadata/data links.
- Search requires at least two characters, caps the response at 20 records, applies a 15-second upstream timeout, a 20-requests/minute rate limit and a 5-minute cache.
- Data Library includes a NASA Earthdata CMR panel, separate from the Copernicus STAC panel.
- Discovery is public metadata only; downloading product files may require Earthdata Login and product-specific access conditions.
- Automated tests cover field mapping, query parameters, caching and upstream failure behavior.
- This connector currently discovers collections, not granules. NASA CMR granule search and direct file access are subsequent integration steps.

## Next phases

1. Add NASA CMR granule discovery by collection, region and period, preserving concept IDs, granule IDs, cloud cover where provided and official access links.
2. Add one direct data adapter for a product with reliable public access and a testable sample file.
3. Add provider selection in analysis settings and a provenance panel for every result.
4. Compare normalized outputs against Earth Engine, with unit, quality-flag and temporal-coverage checks, before any engine migration.


## Endpoint maintenance note

The connector uses the current official STAC endpoint documented by Copernicus Data Space: `https://stac.dataspace.copernicus.eu/v1`. The older `stac.opensearch.dataspace.copernicus.eu` host returned an upstream request-rejected HTML response for POST item searches, so it must not be used for the spatial Item Search adapter.
