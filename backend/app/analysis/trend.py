"""Motor estatístico de tendências: Mann-Kendall (também sazonal), declive de Sen com intervalo
de confiança e regressão linear de comparação.

Só precisa de numpy (o scipy é opcional e serve apenas para o valor-p da regressão linear).
Tudo o que a API devolve como "tendência" sai daqui; nada é preenchido à mão.
"""
import math
from statistics import NormalDist

import numpy as np

_NORMAL = NormalDist()
MAX_POINTS = 1500

DIRECTION_LABELS = {
    "increasing": "Aumento",
    "decreasing": "Diminuição",
    "no_trend": "Sem tendência estatisticamente identificável",
    "inconclusive": "Inconclusivo",
}

STATIC_LIMITATIONS = [
    "O teste de Mann-Kendall deteta tendências monótonas; não identifica causas. Variabilidade natural, "
    "mudanças de sensor ou de constelação de satélites e alterações climáticas podem produzir tendências parecidas.",
    "Significância estatística não é o mesmo que importância ambiental.",
    "Num período curto, a variabilidade de baixa frequência (por exemplo El Niño e La Niña) pode parecer uma tendência.",
]
SEASONAL_LIMITATION = ("O Mann-Kendall sazonal assume independência entre meses; "
                       "a correlação entre meses pode sobrestimar a significância.")


# ------------------------------------------------------------ Mann-Kendall

def mk_statistic(x):
    """S de Mann-Kendall e Var(S) com correção de empates. x ordenado no tempo, sem NaN."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return 0.0, 0.0
    iu, ju = np.triu_indices(n, k=1)
    s = float(np.sign(x[ju] - x[iu]).sum())
    _, counts = np.unique(x, return_counts=True)
    t = counts[counts > 1].astype(float)
    ties = float((t * (t - 1) * (2 * t + 5)).sum())
    return s, (n * (n - 1) * (2 * n + 5) - ties) / 18.0


def mk_z_p(s, var):
    """Z com correção de continuidade e valor-p bicaudal (aproximação normal)."""
    if not var > 0:
        return float("nan"), float("nan")
    if s > 0:
        z = (s - 1.0) / math.sqrt(var)
    elif s < 0:
        z = (s + 1.0) / math.sqrt(var)
    else:
        z = 0.0
    return z, math.erfc(abs(z) / math.sqrt(2.0))


# --------------------------------------------------------------- Sen's slope

def pairwise_slopes(t, x):
    """Declives (x_j - x_i) / (t_j - t_i) de todos os pares i<j com tempos diferentes."""
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    iu, ju = np.triu_indices(len(x), k=1)
    dt = t[ju] - t[iu]
    ok = dt > 0
    return (x[ju] - x[iu])[ok] / dt[ok]


def _rank_value(sorted_vals, rank):
    """Valor na posição 'rank' (1 = menor), com interpolação linear entre posições."""
    n = len(sorted_vals)
    pos = min(max(rank - 1.0, 0.0), n - 1.0)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def sen_confidence_interval(slopes, var_s, alpha):
    """Intervalo de confiança do declive de Sen (Gilbert, 1987), a partir de Var(S)."""
    n = len(slopes)
    if n == 0 or not var_s > 0:
        return float("nan"), float("nan")
    c = _NORMAL.inv_cdf(1.0 - alpha / 2.0) * math.sqrt(var_s)
    srt = np.sort(np.asarray(slopes, dtype=float))
    return _rank_value(srt, (n - c) / 2.0), _rank_value(srt, (n + c) / 2.0 + 1.0)


# ------------------------------------------------------- regressão e resíduos

def _ols(t, x):
    """Regressão linear, só para comparação com o declive de Sen."""
    if len(x) < 3 or float(np.ptp(t)) == 0.0:
        return None
    try:
        from scipy import stats
    except ImportError:
        slope, intercept = np.polyfit(t, x, 1)
        ss_res = float(np.sum((x - (slope * t + intercept)) ** 2))
        ss_tot = float(np.sum((x - x.mean()) ** 2))
        return {"slope_per_year": float(slope), "intercept": float(intercept),
                "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0, "p_value": None}
    r = stats.linregress(t, x)
    return {"slope_per_year": float(r.slope), "intercept": float(r.intercept),
            "r2": float(r.rvalue ** 2), "p_value": float(r.pvalue)}


def _lag1(resid, t, step):
    """Correlação entre resíduos de observações consecutivas (separadas por 'step' anos)."""
    adjacent = np.abs(np.diff(t) - step) < 0.01 * step
    a, b = resid[:-1][adjacent], resid[1:][adjacent]
    if len(a) < 8 or a.std() == 0 or b.std() == 0:
        return None, int(len(a))
    return float(np.corrcoef(a, b)[0, 1]), int(len(a))


# --------------------------------------------------------------- análise

def analyze_trend(t, x, season=None, alpha=0.05, min_years=10, step=1.0, expected_n=None):
    """Analisa uma série temporal.

    t: tempo em anos decimais. x: valores (NaN são ignorados e contados).
    season: se for dado (ex.: o mês de cada ponto), usa o Mann-Kendall sazonal.
    step: espaçamento normal entre pontos, em anos (1 para anual, 1/12 para mensal).
    Devolve um dicionário; se os dados não chegam, direction='inconclusive' com a razão.
    """
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    sea = None if season is None else np.asarray(season)
    ok = np.isfinite(t) & np.isfinite(x)
    t, x = t[ok], x[ok]
    if sea is not None:
        sea = sea[ok]
    order = np.argsort(t, kind="stable")
    t, x = t[order], x[order]
    if sea is not None:
        sea = sea[order]
    n = int(len(x))
    n_years = int(len(np.unique(np.floor(t)))) if n else 0
    seasonal = sea is not None
    out = {
        "method": ("Mann-Kendall sazonal (Hirsch-Slack) + declive de Sen sazonal" if seasonal
                   else "Mann-Kendall + declive de Sen"),
        "alpha": alpha, "n_observations": n, "n_years": n_years, "expected_observations": expected_n,
        "limitations": list(STATIC_LIMITATIONS) + ([SEASONAL_LIMITATION] if seasonal else []),
        "warnings": [],
    }

    def inconclusive(reason):
        out.update(direction="inconclusive", direction_label=DIRECTION_LABELS["inconclusive"],
                   significant=False, reason=reason, mann_kendall=None, sen=None, ols=None,
                   autocorrelation_lag1=None)
        return out

    if n < 3:
        return inconclusive("menos de 3 observações válidas")
    if n > MAX_POINTS:
        return inconclusive("série demasiado longa (%d pontos; máximo %d)" % (n, MAX_POINTS))
    if n_years < min_years:
        return inconclusive("dados insuficientes: %d anos com dados, mínimo %d" % (n_years, min_years))
    if float(np.ptp(x)) == 0.0:
        return inconclusive("série constante: não há variabilidade para testar")

    if seasonal:
        s_tot, var_tot, parts = 0.0, 0.0, []
        for k in np.unique(sea):
            idx = np.where(sea == k)[0]
            if len(idx) < 2:
                continue
            s_k, v_k = mk_statistic(x[idx])
            s_tot += s_k
            var_tot += v_k
            parts.append(pairwise_slopes(t[idx], x[idx]))
        slopes = np.concatenate(parts) if parts else np.array([])
    else:
        s_tot, var_tot = mk_statistic(x)
        slopes = pairwise_slopes(t, x)
    z, p = mk_z_p(s_tot, var_tot)
    if math.isnan(p) or slopes.size == 0:
        return inconclusive("não foi possível estimar a variância do teste (valores repetidos a mais ou pares a menos)")

    slope = float(np.median(slopes))
    ci_low, ci_high = sen_confidence_interval(slopes, var_tot, alpha)
    intercept = float(np.median(x - slope * t))
    significant = bool(p < alpha)
    direction = ("increasing" if s_tot > 0 else "decreasing") if significant else "no_trend"

    warnings = out["warnings"]
    if expected_n and n / float(expected_n) < 0.9:
        warnings.append("Faltam %.0f%% das observações esperadas (%d de %d)."
                        % (100.0 * (1.0 - n / float(expected_n)), n, expected_n))
    if n_years < 20:
        warnings.append("Série curta (%d anos): o poder do teste é limitado e a tendência pode refletir "
                        "variabilidade natural." % n_years)
    if (n - len(np.unique(x))) / float(n) > 0.1:
        warnings.append("Mais de 10% dos valores são repetidos (muitos zeros?). O teste corrige os empates, "
                        "mas perde sensibilidade.")
    if significant and (slope == 0 or (slope > 0) != (s_tot > 0)):
        warnings.append("O declive de Sen (mediana dos declives) não acompanha o sentido do teste, "
                        "provavelmente por valores repetidos. Interprete com cuidado.")

    detrended = x - slope * t
    resid = detrended - np.median(detrended)
    if seasonal:
        resid = detrended.copy()
        for k in np.unique(sea):
            m = sea == k
            resid[m] = detrended[m] - np.median(detrended[m])
    r1, pairs = _lag1(resid, t, step)
    if r1 is not None and abs(r1) > 2.0 / math.sqrt(pairs):
        if r1 > 0:
            warnings.append("Autocorrelação positiva nos resíduos (lag-1 = %.2f): o valor-p pode estar "
                            "subestimado. Considere pré-branqueamento ou a variante de Yue-Wang." % r1)
        else:
            warnings.append("Autocorrelação negativa nos resíduos (lag-1 = %.2f): o teste tende a ser "
                            "conservador." % r1)

    ols = _ols(t, x)
    if ols is not None and seasonal:
        ols["note"] = "calculada sobre a série bruta (inclui o ciclo sazonal); serve só de comparação"

    out.update(
        direction=direction, direction_label=DIRECTION_LABELS[direction], significant=significant, reason=None,
        mann_kendall={"s": s_tot, "var_s": var_tot, "z": z, "p_value": p},
        sen={"slope_per_year": slope, "ci_level": 1.0 - alpha, "ci_low": ci_low, "ci_high": ci_high,
             "intercept": intercept},
        ols=ols, autocorrelation_lag1=r1)
    return out
