"""Leitura dos dados descarregados da NASA: grelhas NetCDF/HDF5 (via xarray) ou séries CSV já agregadas."""
import csv
import datetime
import glob
import math
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np

from ..errors import ApiError
from .containers import Cube, Series

META_KEYS = ("title", "product_version", "algorithm_version", "version", "processing_level",
             "institution", "source", "doi", "DOI")
MISSING_TOKENS = {"", "nan", "null", "none", "na", "n/a", "--"}
FILL_THRESHOLD = -9990.0          # valores <= isto (ex.: -9999.9) são preenchimentos, não medições
_ALIASES = {
    "time": ("time", "Time", "valid_time", "date"),
    "lat": ("lat", "latitude", "Latitude", "y"),
    "lon": ("lon", "longitude", "Longitude", "x"),
}


def _modified(path):
    ts = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat()


def _ym_str(ym):
    return "%04d-%02d" % ym


# ------------------------------------------------------------------ grelhas

def _need_xarray():
    try:
        import xarray as xr
    except ImportError as exc:
        raise ApiError(500, "missing_dependency",
                       "O servidor não tem o xarray e o netCDF4 instalados (pip install -r requirements.txt).") from exc
    return xr


def _open_variable(xr, path, variable, group):
    """Abre o ficheiro e procura a variável na raiz e no grupo 'Grid' (formato HDF5 do IMERG)."""
    tried = []
    for g in dict.fromkeys([group, None, "Grid"]):
        try:
            ds = xr.open_dataset(path, group=g)
        except Exception as exc:        # grupo inexistente, ficheiro ilegível...
            tried.append("%s: %s" % (g or "raiz", type(exc).__name__))
            continue
        if variable in ds.variables:
            return ds
        ds.close()
        tried.append("%s: sem a variável" % (g or "raiz"))
    raise ApiError(422, "variable_not_found",
                   "A variável %r não foi encontrada em %s (%s). Corra: python -m app.data.describe <ficheiro>"
                   % (variable, os.path.basename(path), "; ".join(tried)))


def _standardize(da):
    """Nomes time/lat/lon, tempo como dimensão e eixos por ordem crescente."""
    rename = {}
    for std, names in _ALIASES.items():
        if std in da.dims or std in da.coords:
            continue
        for n in names:
            if n in da.dims or n in da.coords:
                rename[n] = std
                break
    if rename:
        da = da.rename(rename)
    if "time" not in da.dims and "time" in da.coords:
        da = da.expand_dims("time")
    for need in ("time", "lat", "lon"):
        if need not in da.dims:
            raise ApiError(422, "bad_grid", "A variável não tem a dimensão %r (tem: %s)."
                           % (need, ", ".join(map(str, da.dims))))
    extra = [d for d in da.dims if d not in ("time", "lat", "lon")]
    if extra:
        raise ApiError(422, "bad_grid", "A variável tem dimensões a mais: %s." % ", ".join(map(str, extra)))
    return da.sortby("lat").sortby("lon")


def load_cube(files, dataset, bbox, start, end):
    """Lê só a região e o período pedidos de cada ficheiro e junta-os por ordem de tempo."""
    xr = _need_xarray()
    variable = dataset["variable"]
    parts, ym_all, seen = [], [], []
    lats = lons = None
    unit, meta, infos, masked = None, {}, [], 0
    for path in files:
        name = os.path.basename(path)
        ds = _open_variable(xr, path, variable, dataset.get("group"))
        try:
            da = _standardize(ds[variable])
            ym = [(int(t.year), int(t.month)) for t in da.indexes["time"]]
            seen.extend(ym)
            pick = [i for i, v in enumerate(ym) if start <= v <= end]
            if not pick:
                continue
            da = da.isel(time=pick).sel(lat=slice(bbox["lat_min"], bbox["lat_max"]),
                                        lon=slice(bbox["lon_min"], bbox["lon_max"]))
            if da.sizes["lat"] == 0 or da.sizes["lon"] == 0:
                raise ApiError(422, "region_outside_data", "A região fica fora da área coberta por %s." % name)
            arr = np.array(da.values, dtype=float)
            u = da.attrs.get("units")
            if unit is None:
                unit = u
            elif u is not None and str(u) != str(unit):
                raise ApiError(422, "units_differ", "Os ficheiros têm unidades diferentes (%r e %r)." % (unit, u))
            la, lo = np.asarray(da["lat"].values, dtype=float), np.asarray(da["lon"].values, dtype=float)
            if lats is None:
                lats, lons = la, lo
            elif la.shape != lats.shape or lo.shape != lons.shape or not (
                    np.allclose(la, lats) and np.allclose(lo, lons)):
                raise ApiError(422, "grid_differs", "%s tem uma grelha diferente dos outros ficheiros." % name)
            vmin = dataset.get("valid_min")
            if vmin is not None:
                bad = arr < vmin
                masked += int(bad.sum())
                arr[bad] = np.nan
            for k in META_KEYS:
                if k in ds.attrs and k not in meta:
                    meta[k] = str(ds.attrs[k])[:200]
            parts.append(arr)
            ym_all.extend(ym[i] for i in pick)
            infos.append({"name": name, "modified": _modified(path)})
        finally:
            ds.close()
    if not parts:
        cover = " Cobertura dos ficheiros: %s a %s." % (_ym_str(min(seen)), _ym_str(max(seen))) if seen else ""
        raise ApiError(422, "no_data_in_period", "Os ficheiros não têm dados entre %s e %s.%s"
                       % (_ym_str(start), _ym_str(end), cover))
    dupes = sorted(k for k, c in Counter(ym_all).items() if c > 1)
    if dupes:
        raise ApiError(422, "duplicate_months",
                       "Meses repetidos (%s...). Deve haver um passo por mês: confirme que descarregou o produto "
                       "mensal e que não há duas versões do mesmo mês na pasta." % ", ".join(map(_ym_str, dupes[:3])))
    order = sorted(range(len(ym_all)), key=lambda i: ym_all[i])
    values = np.concatenate(parts, axis=0)
    if order != list(range(len(order))):
        values = values[order]
    return Cube([ym_all[i] for i in order], lats, lons, values, unit, infos, meta, masked)


# -------------------------------------------------------------------- CSV

def _parse_ym(cell):
    m = (re.match(r"^\s*(\d{4})-(\d{2})(?:-\d{2})?(?:[T ].*)?$", cell)
         or re.match(r"^\s*(\d{4})(\d{2})\s*$", cell))
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return (y, mo) if 1 <= mo <= 12 else None


def _parse_value(cell):
    c = cell.strip().lower()
    if c in MISSING_TOKENS:
        return float("nan"), False
    v = float(c)                      # ValueError se não for número
    if not math.isfinite(v):
        return float("nan"), False
    if v <= FILL_THRESHOLD:
        return float("nan"), True
    return v, False


def load_series_csv(path, start, end, valid_min=None):
    """CSV com data na 1.ª coluna e valor na 2.ª, com as unidades numa linha '# units: ...'.

    Linhas antes da primeira data (cabeçalhos, metadados do Giovanni) são ignoradas;
    '# chave: valor' guarda metadados. As unidades nunca são assumidas.
    """
    path = Path(path)
    unit, meta, rows, masked = None, {}, {}, 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for lineno, line in enumerate(fh, 1):
            text = line.strip()
            if not text:
                continue
            if text.startswith("#"):
                key, _, val = text[1:].partition(":")
                key, val = key.strip().lower(), val.strip()
                if key in ("units", "unit", "unidade", "unidades"):
                    unit = val or None
                elif key and val:
                    meta[key] = val[:200]
                continue
            cells = next(csv.reader([text]))
            ym = _parse_ym(cells[0])
            if ym is None:
                if rows:
                    raise ApiError(422, "bad_csv", "%s, linha %d: data inválida %r." % (path.name, lineno, cells[0]))
                continue
            if len(cells) < 2:
                raise ApiError(422, "bad_csv", "%s, linha %d: falta a coluna do valor." % (path.name, lineno))
            try:
                value, was_fill = _parse_value(cells[1])
            except ValueError:
                raise ApiError(422, "bad_csv", "%s, linha %d: valor inválido %r." % (path.name, lineno, cells[1]))
            if ym in rows:
                raise ApiError(422, "duplicate_months", "%s: o mês %s aparece mais de uma vez." % (path.name, _ym_str(ym)))
            if valid_min is not None and value < valid_min:
                value, was_fill = float("nan"), True
            rows[ym] = value
            masked += int(was_fill)
    if not rows:
        raise ApiError(422, "bad_csv", "%s não tem linhas com data e valor." % path.name)
    if not unit:
        raise ApiError(422, "units_missing",
                       "O CSV %s não declara as unidades. Acrescente no topo uma linha como '# units: mm/day' "
                       "(confirme-as nos metadados do produto): o backend não assume unidades." % path.name)
    all_ym = sorted(rows)
    pick = [k for k in all_ym if start <= k <= end]
    if not pick:
        raise ApiError(422, "no_data_in_period", "%s não tem dados entre %s e %s (cobertura: %s a %s)."
                       % (path.name, _ym_str(start), _ym_str(end), _ym_str(all_ym[0]), _ym_str(all_ym[-1])))
    return Series(pick, np.array([rows[k] for k in pick], dtype=float), unit,
                  [{"name": path.name, "modified": _modified(path)}], meta, masked)


# ----------------------------------------------------------------- carregador

class FileLoader:
    """Procura os dados do dataset em data/raw/<id>/ e devolve um Cube (grelha) ou uma Series (CSV)."""

    def __init__(self, raw_dir):
        self.raw_dir = Path(raw_dir)

    def grid_files(self, dataset):
        folder = self.raw_dir / dataset["id"]
        found = set()
        for pattern in dataset.get("file_patterns", ["*.nc", "*.nc4"]):
            found.update(glob.glob(str(folder / pattern)))
        return sorted(found)

    def series_path(self, dataset, region_id):
        return self.raw_dir / dataset["id"] / "series" / ("%s.csv" % region_id)

    def available(self, dataset):
        folder = self.raw_dir / dataset["id"]
        return {"grid_files": len(self.grid_files(dataset)),
                "series_files": len(glob.glob(str(folder / "series" / "*.csv")))}

    def load(self, dataset, region, start, end):
        files = self.grid_files(dataset)
        if files:
            return load_cube(files, dataset, region["bbox"], start, end)
        csv_path = self.series_path(dataset, region["id"])
        if csv_path.is_file():
            return load_series_csv(csv_path, start, end, dataset.get("valid_min"))
        raise ApiError(
            409, "data_unavailable",
            "Ainda não há dados de %r no servidor. Coloque os ficheiros NetCDF/HDF5 descarregados em "
            "data/raw/%s/ (ou, para uma região já agregada, um CSV em data/raw/%s/series/%s.csv). "
            "Veja data/README.md." % (dataset["id"], dataset["id"], dataset["id"], region["id"]),
            {"dataset_id": dataset["id"], "folder": "data/raw/%s" % dataset["id"]})
