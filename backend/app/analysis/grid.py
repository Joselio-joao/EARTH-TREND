"""Grelhas lat/lon: máscaras de região, média ponderada por área e redução para mapa."""
import math
import warnings

import numpy as np


def bbox_mask(lons, lats, bbox):
    """Células cujo centro está dentro da caixa. Devolve bool (lat, lon)."""
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    lat_ok = (lats >= bbox["lat_min"]) & (lats <= bbox["lat_max"])
    lon_ok = (lons >= bbox["lon_min"]) & (lons <= bbox["lon_max"])
    return lat_ok[:, None] & lon_ok[None, :]


def rings_from_geojson(obj):
    """Todos os anéis (contornos e buracos) de Polygon/MultiPolygon, como listas de (lon, lat)."""
    rings = []

    def visit(g):
        if not isinstance(g, dict):
            return
        kind = g.get("type")
        if kind == "FeatureCollection":
            for f in g.get("features", []):
                visit(f)
        elif kind == "Feature":
            visit(g.get("geometry"))
        elif kind == "GeometryCollection":
            for x in g.get("geometries", []):
                visit(x)
        elif kind == "Polygon":
            for ring in g.get("coordinates", []):
                rings.append([(float(p[0]), float(p[1])) for p in ring])
        elif kind == "MultiPolygon":
            for poly in g.get("coordinates", []):
                for ring in poly:
                    rings.append([(float(p[0]), float(p[1])) for p in ring])

    visit(obj)
    return rings


def rings_bbox(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return {"lat_min": min(ys), "lat_max": max(ys), "lon_min": min(xs), "lon_max": max(xs)}


def polygon_mask(lons, lats, rings):
    """Regra par-ímpar (ray casting): True onde o centro da célula está dentro dos polígonos."""
    px, py = np.meshgrid(np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
    inside = np.zeros(px.shape, dtype=bool)
    for ring in rings:
        pts = np.asarray(ring, dtype=float)
        if len(pts) < 3:
            continue
        if not np.array_equal(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[:1]])
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            if ya == yb:
                continue
            cross = (ya > py) != (yb > py)
            if not cross.any():
                continue
            xint = xa + (py[cross] - ya) * (xb - xa) / (yb - ya)
            flip = np.zeros(px.shape, dtype=bool)
            flip[cross] = px[cross] < xint
            inside ^= flip
    return inside


def area_weighted_mean(values, lats, mask=None):
    """Média espacial ponderada por cos(lat), ignorando NaN e células fora da máscara.

    values: (tempo, lat, lon). Devolve (média por passo, nº de células usadas por passo).
    Passo a passo, para não multiplicar a memória do pedido.
    """
    v = np.asarray(values, dtype=float)
    if v.ndim == 2:
        v = v[None]
    w = np.cos(np.deg2rad(np.asarray(lats, dtype=float)))[:, None] * np.ones((1, v.shape[2]))
    if mask is not None:
        w = w * np.asarray(mask, dtype=float)
    means = np.full(v.shape[0], np.nan)
    counts = np.zeros(v.shape[0], dtype=int)
    for k in range(v.shape[0]):
        ok = np.isfinite(v[k]) & (w > 0)
        den = float(w[ok].sum())
        if den > 0:
            means[k] = float((v[k][ok] * w[ok]).sum() / den)
        counts[k] = int(ok.sum())
    return means, counts


def time_mean(values):
    """Média no tempo, célula a célula, ignorando NaN (NaN se a célula nunca tem dados)."""
    v = np.asarray(values, dtype=float)
    total = np.zeros(v.shape[1:])
    count = np.zeros(v.shape[1:], dtype=int)
    for k in range(v.shape[0]):
        ok = np.isfinite(v[k])
        total[ok] += v[k][ok]
        count += ok
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def coarsen(field, lats, lons, max_cells=40):
    """Média por blocos para o mapa não passar de max_cells células no lado maior."""
    field = np.asarray(field, dtype=float)
    ny, nx = field.shape
    f = max(1, int(math.ceil(max(ny, nx) / float(max_cells))))
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    if f == 1:
        return field, lats, lons
    py, px = (-ny) % f, (-nx) % f
    big = np.pad(field, ((0, py), (0, px)), constant_values=np.nan)
    la = np.pad(lats, (0, py), constant_values=np.nan)
    lo = np.pad(lons, (0, px), constant_values=np.nan)
    ny2, nx2 = big.shape[0] // f, big.shape[1] // f
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = np.nanmean(big.reshape(ny2, f, nx2, f), axis=(1, 3))
        lat2 = np.nanmean(la.reshape(ny2, f), axis=1)
        lon2 = np.nanmean(lo.reshape(nx2, f), axis=1)
    return out, lat2, lon2


def make_map(field, lats, lons, unit, statistic, max_cells=40):
    """Grelha pronta para o Leaflet: values[j][i] corresponde a lats[j] (crescente) e lons[i]."""
    f, la, lo = coarsen(field, lats, lons, max_cells)
    finite = f[np.isfinite(f)]
    return {
        "lats": la.tolist(), "lons": lo.tolist(), "values": f.tolist(),
        "unit": unit, "statistic": statistic,
        "cell_size_deg": [float(np.median(np.diff(la))) if len(la) > 1 else None,
                          float(np.median(np.diff(lo))) if len(lo) > 1 else None],
        "min": float(finite.min()) if finite.size else None,
        "max": float(finite.max()) if finite.size else None,
    }
