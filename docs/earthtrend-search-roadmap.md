# EarthTrend Search — architecture and migration plan

**Status:** phase 1 (local metadata search)  
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
- NASA Earthdata CMR: **planned** discovery adapter; collection/granule search and links.
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

## Phase 1 implemented

- Local metadata search endpoint: /search/catalog.
- Provider state endpoint: /search/status.
- Search UI in Data Library.
- Search ranks matching dataset metadata and exposes status, source, coverage, units, resolution and official link.
- It does **not** search remote NASA collections or retrieve data yet.

## Next phases

1. Validate the search endpoint and frontend build.
2. Add remote CMR collection discovery with product IDs and official links.
3. Add direct data adapters, beginning with a product that has reliable public access and small sample files.
4. Add provider selection in analysis settings and a provenance panel for every result.
5. Compare results against Earth Engine and tests before any engine migration.
