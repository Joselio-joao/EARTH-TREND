"""Uma análise de ponta a ponta: confere unidades, agrega no tempo, faz a média espacial,
calcula a tendência e o mapa. Não sabe nada de HTTP nem de ficheiros."""
import math

import numpy as np

from ..data.containers import Cube
from ..errors import ApiError
from . import grid, timeops
from .interpret import interpret
from .trend import analyze_trend

SCALE_LABELS = {"monthly": "mensal", "seasonal": "sazonal", "annual": "anual"}


def _trend_map(data, lats, lons, mask, t, season, alpha, min_years, step, unit):
    """Calcula uma tendência compacta para cada célula válida da grelha.

    A grelha é reduzida ao mesmo limite visual do mapa normal (40 células por lado).
    Células fora da região permanecem nulas e não entram no teste estatístico.
    """
    masked = np.asarray(data, dtype=float).copy()
    masked[:, ~mask] = np.nan
    reduced = [grid.coarsen(frame, lats, lons, max_cells=40)[0] for frame in masked]
    values = np.asarray(reduced, dtype=float)
    _, out_lats, out_lons = grid.coarsen(masked[0], lats, lons, max_cells=40)
    shape = values.shape[1:]
    directions = [[None for _ in range(shape[1])] for _ in range(shape[0])]
    slopes = np.full(shape, np.nan)
    p_values = np.full(shape, np.nan)
    significant = np.full(shape, False, dtype=bool)
    observations = np.zeros(shape, dtype=int)

    for iy in range(shape[0]):
        for ix in range(shape[1]):
            cell = analyze_trend(t, values[:, iy, ix], season=season, alpha=alpha,
                                 min_years=min_years, step=step, expected_n=len(t))
            directions[iy][ix] = cell["direction"] if cell["n_observations"] else None
            observations[iy, ix] = cell["n_observations"]
            significant[iy, ix] = bool(cell["significant"])
            if cell.get("mann_kendall"):
                p_values[iy, ix] = cell["mann_kendall"]["p_value"]
            if cell.get("sen"):
                slopes[iy, ix] = cell["sen"]["slope_per_year"]

    return to_jsonable({
        "lats": out_lats.tolist(), "lons": out_lons.tolist(),
        "directions": directions, "slopes_per_year": slopes,
        "p_values": p_values, "significant": significant,
        "observations": observations, "unit_per_year": "%s por ano" % unit,
        "statistic": "Declive de Sen e Mann-Kendall por célula",
        "cell_size_deg": [float(np.median(np.diff(out_lats))) if len(out_lats) > 1 else None,
                          float(np.median(np.diff(out_lons))) if len(out_lons) > 1 else None],
    })


def to_jsonable(obj):
    """Converte tipos numpy e troca NaN/inf por None, para o JSON ser válido."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [to_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    return obj


def run_analysis(dataset, region, req, source, min_years=10):
    """req (já validado pelo serviço): start, end, load_start (tuplos ano-mês), scale, season_months,
    season_label, alpha, question. source: Cube (grelha) ou Series (já agregada na região)."""
    kind = dataset["value_kind"]
    start, end, scale, alpha = req["start"], req["end"], req["scale"], req["alpha"]
    load_start = req.get("load_start", start)
    season_months, season_code = req.get("season_months"), req.get("season_label")
    notes = []

    # 1. Unidades: nunca se assumem nem se tratam taxas como acumulações.
    unit_in = source.unit or dataset.get("native_unit")
    if not source.unit:
        notes.append("Os dados não declaram unidades; foi usada a do registo (%s). Confirme-a na documentação "
                     "do produto." % unit_in)
    accepted = dataset.get("accepted_units") or [dataset.get("native_unit")]
    if not timeops.unit_matches(unit_in, accepted):
        raise ApiError(422, "unit_mismatch", "Unidade inesperada %r (o registo aceita: %s). Confirme o atributo "
                       "'units' dos dados antes de analisar." % (unit_in, ", ".join(accepted)))
    per_day = None
    if kind == "mean_rate":
        per_day = timeops.rate_per_day_factor(unit_in)
        if per_day is None:
            raise ApiError(422, "unit_mismatch", "A unidade %r não é uma taxa de precipitação reconhecida "
                           "(mm/dia, mm/hora ou mm/s)." % unit_in)

    # 2. Período carregado.
    ym = list(source.ym)
    values = np.asarray(source.values, dtype=float)
    keep = [i for i, v in enumerate(ym) if load_start <= v <= end]
    if not keep:
        raise ApiError(422, "no_data_in_period", "Sem dados entre %s e %s. Cobertura: %s a %s."
                       % (timeops.ym_str(start), timeops.ym_str(end), timeops.ym_str(ym[0]), timeops.ym_str(ym[-1])))
    if len(keep) != len(ym):
        ym = [ym[i] for i in keep]
        values = values[keep]

    # 3. Taxa média do mês -> total do mês.
    if kind == "mean_rate":
        values = timeops.convert_rate_to_totals(values, ym, per_day)
    how = "mean" if kind == "state" else "sum"
    if kind == "state":
        unit_out = dataset.get("display_unit") or unit_in
    else:
        unit_out = {"monthly": "mm/mês", "annual": "mm/ano", "seasonal": "mm/época (%s)" % season_code}[scale]

    # 4. Agregação temporal.
    if scale == "monthly":
        sel = [i for i, v in enumerate(ym) if start <= v <= end]
        ym = [ym[i] for i in sel]
        data = values[sel]
        labels = [timeops.ym_str(v) for v in ym]
        t = np.array([timeops.decimal_year(v) for v in ym])
        season, step = np.array([v[1] for v in ym]), 1.0 / 12.0
        expected, dropped = timeops.months_between(start, end), []
    else:
        months = season_months if scale == "seasonal" else tuple(range(1, 13))
        years, data, dropped = timeops.aggregate_windows(ym, values, months, how)
        sel = [i for i, y in enumerate(years) if start[0] <= y <= end[0]]
        years, data = [years[i] for i in sel], data[sel]
        dropped = [y for y in dropped if start[0] <= y <= end[0]]
        labels, t, season, step = [str(y) for y in years], np.array(years, dtype=float), None, 1.0
        expected = end[0] - start[0] + 1
    if not labels:
        raise ApiError(422, "no_complete_windows",
                       "Não há nenhum período completo entre %s e %s (excluídos por meses em falta: %s)."
                       % (timeops.ym_str(start), timeops.ym_str(end), ", ".join(map(str, dropped)) or "nenhum"))

    # 5. Média espacial e mapa.
    cells_total = cells_used = map_payload = None
    trend_map_payload = None
    if isinstance(source, Cube):
        lats, lons = np.asarray(source.lats, dtype=float), np.asarray(source.lons, dtype=float)
        if region.get("rings"):
            mask = grid.polygon_mask(lons, lats, region["rings"])
        else:
            mask = np.ones((len(lats), len(lons)), dtype=bool)
        mask &= grid.bbox_mask(lons, lats, region["bbox"])
        cells_total = int(mask.sum())
        if cells_total == 0:
            raise ApiError(422, "region_without_cells", "A região não contém nenhum centro de célula da grelha "
                           "(é mais pequena do que a resolução dos dados?).")
        series, counts = grid.area_weighted_mean(data, lats, mask)
        field = grid.time_mean(data)
        field[~mask] = np.nan
        map_payload = grid.make_map(field, lats, lons, unit_out, "Média no período analisado")
        if req.get("include_trend_map"):
            trend_map_payload = _trend_map(data, lats, lons, mask, t, season, alpha, min_years, step, unit_out)
        cells_used = float(np.mean(counts[counts > 0])) if (counts > 0).any() else 0.0
    else:
        series = np.asarray(data, dtype=float)
    if region.get("boundary") in ("bbox", "custom"):
        notes.append("A média usa todas as células da caixa, incluindo oceano e países vizinhos. Para o território "
                     "exato, coloque o contorno oficial em data/regions/<região>.geojson.")

    # 6. Tendência.
    trend = analyze_trend(t, series, season=season, alpha=alpha, min_years=min_years, step=step, expected_n=expected)
    sen = trend["sen"]
    line = None
    trend["magnitude"] = None
    if sen:
        line = sen["intercept"] + sen["slope_per_year"] * t
        mean = float(np.nanmean(series))
        slope = sen["slope_per_year"]
        trend["magnitude"] = {
            "slope_per_year": slope, "unit_per_year": "%s por ano" % unit_out,
            "change_per_decade": slope * 10.0, "unit_per_decade": "%s por década" % unit_out,
            "relative_change_per_decade_pct": 1000.0 * slope / mean if (kind != "state" and mean > 0) else None,
            "ci_level": sen["ci_level"], "ci_low": sen["ci_low"], "ci_high": sen["ci_high"],
        }
    limitations = trend.pop("limitations") + list(dataset.get("limitations", []))
    notes += trend.pop("warnings")

    # 7. Período, qualidade e proveniência.
    first, last = labels[0], labels[-1]
    if scale == "monthly":
        clipped = first != timeops.ym_str(start) or last != timeops.ym_str(end)
    else:
        clipped = int(first) > start[0] or int(last) < end[0]
    if clipped:
        notes.append("O período pedido (%s a %s) não está todo coberto: foram analisados %s a %s."
                     % (timeops.ym_str(start), timeops.ym_str(end), first, last))
    if dropped:
        notes.append("Excluídos por terem meses em falta: %s." % ", ".join(map(str, dropped)))
    valid = int(np.isfinite(series).sum())
    files = list(source.files or [])
    mods = sorted(f["modified"] for f in files)
    scale_text = SCALE_LABELS[scale] + (" (%s)" % season_code if scale == "seasonal" else "")
    interp = interpret(trend, region["name"], dataset["variable_label"], first, last, unit_out, SCALE_LABELS[scale])

    return to_jsonable({
        "status": "inconclusive" if trend["direction"] == "inconclusive" else "ok",
        "request": {
            "dataset_id": dataset["id"], "region_id": req.get("region_id"), "bbox": req.get("bbox"),
            "start": timeops.ym_str(start), "end": timeops.ym_str(end), "scale": scale, "season": season_code,
            "season_months": list(season_months) if season_months else None, "alpha": alpha,
            "include_trend_map": bool(req.get("include_trend_map")),
            "question": req.get("question"),
        },
        "dataset": {k: dataset[k] for k in ("id", "name", "family", "provider", "version", "product_short_name",
                                            "product_url", "doi", "citation", "license") if k in dataset},
        "variable": {"id": dataset["variable_id"], "label": dataset["variable_label"]},
        "region": {"id": region["id"], "name": region["name"], "bbox": region["bbox"],
                   "boundary": region["boundary"], "approximate": region["approximate"], "cells": cells_total},
        "period": {"requested": {"start": timeops.ym_str(start), "end": timeops.ym_str(end)},
                   "analyzed": {"first": first, "last": last}, "clipped": clipped},
        "scale": scale, "scale_label": scale_text, "unit": unit_out,
        "series": {"labels": labels, "t": t, "values": series,
                   "trend_line": line, "unit": unit_out},
        "trend": trend,
        "interpretation": interp,
        "data_quality": {
            "expected_steps": expected, "valid_steps": valid,
            "valid_fraction": valid / float(expected) if expected else None,
            "incomplete_windows_dropped": dropped, "cells_in_region": cells_total,
            "cells_used_mean": cells_used, "masked_invalid_values": int(source.masked_invalid),
        },
        "provenance": {
            "dataset_id": dataset["id"], "product": dataset.get("product_short_name"),
            "version": dataset.get("version"), "provider": dataset.get("provider"), "doi": dataset.get("doi"),
            "citation": dataset.get("citation"), "license": dataset.get("license"),
            "product_url": dataset.get("product_url"), "unit_in_data": unit_in,
            "unit_declared_in_data": bool(source.unit), "files": files,
            "files_modified": {"first": mods[0], "last": mods[-1]} if mods else None,
            "file_attributes": dict(source.meta or {}),
            "note": "As datas dos ficheiros são as da cópia local (aproximam a data de descarga).",
        },
        "warnings": notes,
        "limitations": limitations,
        "map": map_payload,
        "trend_map": trend_map_payload,
    })
