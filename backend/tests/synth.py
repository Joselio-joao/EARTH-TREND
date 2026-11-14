"""Dados SINTÉTICOS, só para os testes. Nunca representam observações da NASA."""
import numpy as np

from app.analysis import timeops
from app.config import PACKAGE_DATA
from app.data.containers import Cube
from app.data.registry import Registry

REGISTRY = Registry.load(PACKAGE_DATA, "/nao/existe")
DATASET = REGISTRY.dataset("gpm_imerg_monthly")
# Os testes sintéticos usam deliberadamente uma caixa fixa. Assim continuam
# independentes dos ficheiros geográficos reais instalados em backend/data.
REGION = {
    "id": "angola", "name": "Angola",
    "bbox": {"lat_min": -18.1, "lat_max": -4.3, "lon_min": 11.6, "lon_max": 24.1},
    "rings": None, "boundary": "bbox", "approximate": True, "note": "fixture sintético",
}


def make_cube(first_year=2005, last_year=2024, rate0=2.0, rate_slope=0.01, unit="mm/day",
              ny=5, nx=5, start_month=1):
    """Taxa constante em cada ano (mm/dia), a crescer rate_slope por ano. Grelha de 1 grau em Angola."""
    ym = [(y, m) for y in range(first_year, last_year + 1) for m in range(1, 13) if (y, m) >= (first_year, start_month)]
    lats = -12.0 + np.arange(ny, dtype=float)
    lons = 14.0 + np.arange(nx, dtype=float)
    values = np.empty((len(ym), ny, nx))
    for i, (y, _) in enumerate(ym):
        values[i] = rate0 + rate_slope * (y - first_year)
    return Cube(ym, lats, lons, values, unit, [{"name": "SINTETICO-teste.nc", "modified": "2000-01-01"}],
                {"synthetic": "true"}, 0)


def make_req(start="2005", end="2024", scale="annual", **kw):
    s, e = timeops.parse_period(start, end)
    req = {"dataset_id": "gpm_imerg_monthly", "region_id": "angola", "bbox": None, "start": s, "end": e,
           "load_start": s, "scale": scale, "season_months": None, "season_label": None, "alpha": 0.05,
           "question": None}
    req.update(kw)
    return req
