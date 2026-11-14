"""Períodos, unidades e agregações temporais (mensal, época do ano, anual)."""
import calendar
import re

import numpy as np

SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}
SCALES = ("monthly", "seasonal", "annual", "native")


# ----------------------------------------------------------------- períodos

def parse_bound(text, is_end):
    """'2015', '2015-03' ou '2015-03-17' -> (ano, mês). Sem mês: janeiro no início, dezembro no fim."""
    m = re.fullmatch(r"\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?\s*", str(text))
    if not m:
        raise ValueError("data inválida %r: use AAAA, AAAA-MM ou AAAA-MM-DD" % (text,))
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else (12 if is_end else 1)
    if not 1900 <= year <= 2200 or not 1 <= month <= 12:
        raise ValueError("data fora do intervalo válido: %r" % (text,))
    return year, month


def ym_str(ym):
    return "%04d-%02d" % (ym[0], ym[1])


def parse_period(start, end):
    s, e = parse_bound(start, False), parse_bound(end, True)
    if s > e:
        raise ValueError("a data final (%s) é anterior à inicial (%s)" % (ym_str(e), ym_str(s)))
    return s, e


def months_between(a, b):
    """Nº de meses entre a e b, inclusive."""
    return (b[0] - a[0]) * 12 + (b[1] - a[1]) + 1


def decimal_year(ym):
    return ym[0] + (ym[1] - 1) / 12.0


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


# ------------------------------------------------------------------- épocas

def validate_season_months(months):
    """Meses consecutivos (podem atravessar o ano, ex.: [12, 1, 2]). Devolve um tuplo."""
    try:
        m = [int(x) for x in months]
    except (TypeError, ValueError):
        raise ValueError("season_months deve ser uma lista de números de 1 a 12")
    if not m or len(m) > 11 or len(set(m)) != len(m) or any(x < 1 or x > 12 for x in m):
        raise ValueError("season_months: use de 1 a 11 meses diferentes, entre 1 e 12")
    for a, b in zip(m, m[1:]):
        if b != a % 12 + 1:
            raise ValueError("season_months: os meses devem ser consecutivos, ex.: [12, 1, 2]")
    return tuple(m)


def season_label(months):
    for name, ms in SEASONS.items():
        if tuple(months) == ms:
            return name
    return "%02d-%02d" % (months[0], months[-1])


def aggregate_windows(ym, values, months, how="sum"):
    """Agrega por janela anual ou sazonal. values tem o tempo no primeiro eixo.

    O ano de uma época que atravessa o fim do ano é o do último mês (DJF 2015 = dez 2014 + jan + fev 2015).
    Janelas com meses em falta são excluídas, nunca preenchidas.
    Devolve (anos, valores agregados, anos excluídos).
    """
    months = tuple(months)
    wraps = months[0] > months[-1]
    groups = {}
    for i, (y, m) in enumerate(ym):
        if m in months:
            groups.setdefault(y + 1 if (wraps and m >= months[0]) else y, []).append(i)
    labels, blocks, dropped = [], [], []
    values = np.asarray(values, dtype=float)
    for label in sorted(groups):
        idx = groups[label]
        if len(idx) != len(months) or len({ym[i][1] for i in idx}) != len(months):
            dropped.append(label)
            continue
        block = values[idx]
        blocks.append(block.sum(axis=0) if how == "sum" else block.mean(axis=0))
        labels.append(label)
    out = np.stack(blocks) if blocks else np.empty((0,) + values.shape[1:])
    return labels, out, dropped


# ---------------------------------------------------------------- unidades

def normalize_unit(unit):
    return re.sub(r"[\s*^]+", "", str(unit or "").strip().lower())


_PER_DAY = {}
for _names, _factor in (
    (("mm/hr", "mm/h", "mm/hour", "mm hr-1", "mm h-1", "mm hour-1"), 24.0),
    (("mm/day", "mm/d", "mm day-1", "mm d-1"), 1.0),
    (("mm/s", "mm s-1", "kg m-2 s-1", "kg/m2/s"), 86400.0),
):
    for _n in _names:
        _PER_DAY[normalize_unit(_n)] = _factor


def rate_per_day_factor(unit):
    """Quantos mm por dia vale 1 unidade da taxa; None se a unidade não for uma taxa de precipitação conhecida."""
    return _PER_DAY.get(normalize_unit(unit))


def unit_matches(unit, accepted):
    return normalize_unit(unit) in {normalize_unit(a) for a in accepted}


def convert_rate_to_totals(values, ym, per_day, inplace=False):
    """Taxa média do mês -> total do mês (mm/mês): taxa x fator x dias do mês.

    Uma taxa nunca se trata como acumulação sem esta conversão.
    """
    values = np.asarray(values, dtype=float)
    factor = np.array([per_day * days_in_month(y, m) for y, m in ym], dtype=float)
    factor = factor.reshape((-1,) + (1,) * (values.ndim - 1))
    if inplace:
        np.multiply(values, factor, out=values)
        return values
    return values * factor
