from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import erfc, sqrt
from statistics import median


@dataclass(frozen=True)
class Observation:
    date: date
    value: float


@dataclass(frozen=True)
class TrendAnalysis:
    n_observations: int
    slope_per_year: float
    intercept: float
    r_squared: float
    sen_slope_per_year: float
    mann_kendall_s: int
    mann_kendall_z: float
    p_value: float
    direction: str
    statistically_significant: bool


def _normal_two_sided_p_value(z: float) -> float:
    return erfc(abs(z) / sqrt(2.0))


def _mann_kendall(values: list[float]) -> tuple[int, float, float]:
    n = len(values)
    s = sum((values[j] > values[i]) - (values[j] < values[i]) for i in range(n) for j in range(i + 1, n))
    counts: dict[float, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    tie_term = sum(count * (count - 1) * (2 * count + 5) for count in counts.values() if count > 1)
    variance = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if variance == 0:
        return s, 0.0, 1.0
    if s > 0:
        z = (s - 1) / sqrt(variance)
    elif s < 0:
        z = (s + 1) / sqrt(variance)
    else:
        z = 0.0
    return s, z, _normal_two_sided_p_value(z)


def _sen_slope(times: list[float], values: list[float]) -> float:
    slopes = [
        (values[j] - values[i]) / (times[j] - times[i])
        for i in range(len(values))
        for j in range(i + 1, len(values))
        if times[j] != times[i]
    ]
    return median(slopes)


def analyze_trend(observations: list[Observation], alpha: float = 0.05) -> TrendAnalysis:
    """Calcula uma tendência temporal sem inferir causalidade."""
    if len(observations) < 3:
        raise ValueError("São necessárias pelo menos 3 observações para analisar uma tendência.")
    ordered = sorted(observations, key=lambda item: item.date)
    if len({item.date for item in ordered}) != len(ordered):
        raise ValueError("As observações não podem repetir a mesma data.")

    origin = ordered[0].date
    times = [(item.date - origin).days / 365.25 for item in ordered]
    values = [float(item.value) for item in ordered]
    mean_time = sum(times) / len(times)
    mean_value = sum(values) / len(values)
    centered_time = [time - mean_time for time in times]
    centered_value = [value - mean_value for value in values]
    denominator = sum(value * value for value in centered_time)
    if denominator == 0:
        raise ValueError("As datas devem representar mais do que um instante temporal.")
    slope = sum(x * y for x, y in zip(centered_time, centered_value)) / denominator
    intercept = mean_value - slope * mean_time
    total_variation = sum(value * value for value in centered_value)
    residual_variation = sum((value - (intercept + slope * time)) ** 2 for time, value in zip(times, values))
    r_squared = 1.0 if total_variation == 0 else max(0.0, 1.0 - residual_variation / total_variation)
    sen_slope = _sen_slope(times, values)
    mk_s, mk_z, p_value = _mann_kendall(values)
    significant = p_value < alpha
    if not significant:
        direction = "sem tendência estatisticamente detetável"
    elif sen_slope > 0:
        direction = "crescente"
    elif sen_slope < 0:
        direction = "decrescente"
    else:
        direction = "sem tendência"

    return TrendAnalysis(
        n_observations=len(ordered),
        slope_per_year=slope,
        intercept=intercept,
        r_squared=r_squared,
        sen_slope_per_year=sen_slope,
        mann_kendall_s=mk_s,
        mann_kendall_z=mk_z,
        p_value=p_value,
        direction=direction,
        statistically_significant=significant,
    )
