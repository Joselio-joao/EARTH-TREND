from typing import TypedDict


class ScientificSource(TypedDict):
    id: str
    dataset_id: str
    product: str
    run: str
    format_options: list[str]
    temporal_options: list[str]
    spatial_resolution: str
    native_units: list[str]
    access_status: str
    source_url: str
    documentation_url: str
    notes: list[str]


SCIENTIFIC_SOURCES: list[ScientificSource] = [
    {
        "id": "nasa-gpm-imerg-final-daily-v07",
        "dataset_id": "gpm-imerg",
        "product": "GPM IMERG Final Precipitation L3 Daily V07",
        "run": "Final",
        "format_options": ["NetCDF", "HDF5", "GeoTIFF"],
        "temporal_options": ["daily", "monthly", "half-hourly"],
        "spatial_resolution": "0.1° × 0.1°",
        "native_units": ["mm/hr", "mm"],
        "access_status": "metadata_registered_file_not_downloaded",
        "source_url": "https://www.earthdata.nasa.gov/dashboard/data-catalog/GPM_3IMERGDF.v07",
        "documentation_url": "https://gpm.nasa.gov/data/imerg",
        "notes": [
            "A NASA identifica o produto diário como uma estimativa Final para investigação.",
            "A unidade e a variável devem ser confirmadas nos atributos do ficheiro descarregado antes da conversão.",
            "A análise espacial deve respeitar a grelha de 0,1° × 0,1° e a região selecionada.",
        ],
    }
]
