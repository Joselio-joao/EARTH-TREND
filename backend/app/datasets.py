from typing import TypedDict


class DatasetRecord(TypedDict):
    id: str
    name: str
    variable: str
    purpose: str
    source: str
    provider: str
    status: str


DATASETS: list[DatasetRecord] = [
    {
        "id": "gpm-imerg",
        "name": "GPM IMERG",
        "variable": "Precipitação",
        "purpose": "Analisar variações e tendências da precipitação.",
        "source": "https://gpm.nasa.gov/data/imerg",
        "provider": "NASA GPM",
        "status": "mvp",
    },
    {
        "id": "modis-ndvi-evi",
        "name": "MODIS NDVI / EVI",
        "variable": "Vegetação",
        "purpose": "Acompanhar mudanças na atividade e vigor da vegetação.",
        "source": "https://modis.gsfc.nasa.gov/data/dataprod/mod13.php",
        "provider": "NASA MODIS",
        "status": "planned",
    },
    {
        "id": "nasa-gistemp",
        "name": "NASA GISTEMP",
        "variable": "Temperatura",
        "purpose": "Investigar tendências de temperatura à superfície.",
        "source": "https://data.giss.nasa.gov/gistemp/",
        "provider": "NASA GISS",
        "status": "planned",
    },
    {
        "id": "nasa-gldas",
        "name": "NASA GLDAS",
        "variable": "Humidade do solo",
        "purpose": "Investigar secas e disponibilidade de água.",
        "source": "https://ldas.gsfc.nasa.gov/gldas/",
        "provider": "NASA GLDAS",
        "status": "planned",
    },
    {
        "id": "grace-grace-fo",
        "name": "GRACE / GRACE-FO",
        "variable": "Armazenamento de água terrestre",
        "purpose": "Identificar mudanças nos recursos hídricos.",
        "source": "https://grace.jpl.nasa.gov/",
        "provider": "NASA GRACE",
        "status": "planned",
    },
    {
        "id": "modis-forest-cover",
        "name": "MODIS Vegetation Cover",
        "variable": "Cobertura florestal",
        "purpose": "Investigar transformação dos ecossistemas.",
        "source": "https://modis.gsfc.nasa.gov/data/",
        "provider": "NASA MODIS",
        "status": "planned",
    },
]
