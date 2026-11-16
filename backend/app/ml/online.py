"""Online unsupervised learning for unusual environmental trend signatures.

The learner is deliberately separate from the scientific trend calculation: it
never changes Mann-Kendall or Sen estimates. It learns a baseline from previous
real analyses and reports how unusual a new analysis looks against that baseline.
"""
import json
import math
import os
import tempfile
import threading
from pathlib import Path

MIN_TRAINING_SAMPLES = 8
ANOMALY_THRESHOLD = 3.0


def _finite(values):
    out = []
    for value in values or []:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            out.append(number)
    return out


def _features(result):
    series = result.get("series") or {}
    values = _finite(series.get("values"))
    if len(values) < 3:
        return None
    median = sorted(values)[len(values) // 2]
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / max(1, len(values) - 1)
    std = math.sqrt(variance)
    scale = max(abs(median), abs(mean), 1e-9)
    trend = result.get("trend") or {}
    sen = trend.get("sen") or {}
    slope = sen.get("slope_per_year")
    try:
        slope = float(slope)
    except (TypeError, ValueError):
        slope = 0.0
    if not math.isfinite(slope):
        slope = 0.0
    period = result.get("period") or {}
    years = period.get("n_years") or period.get("years") or len(values)
    try:
        years = max(1.0, float(years))
    except (TypeError, ValueError):
        years = float(len(values))
    expected = series.get("expected_observations") or len(values)
    try:
        expected = max(len(values), int(expected))
    except (TypeError, ValueError):
        expected = len(values)
    missing_ratio = max(0.0, min(1.0, 1.0 - len(values) / expected))
    mk = trend.get("mann_kendall") or {}
    try:
        p_value = float(mk.get("p_value", 1.0))
    except (TypeError, ValueError):
        p_value = 1.0
    if not math.isfinite(p_value):
        p_value = 1.0
    # Relative features make products with different physical units comparable.
    return [std / scale, (slope * years) / scale, missing_ratio, max(0.0, min(1.0, p_value))]


class OnlineLearningStore:
    """Welford online baseline, persisted atomically as compact JSON."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "online-learning.json"
        self._lock = threading.RLock()
        self._models = self._read()

    def _read(self):
        try:
            with self.path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            models = payload.get("models", {})
            return models if isinstance(models, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=str(self.directory), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "models": self._models}, handle, ensure_ascii=False, allow_nan=False)
            os.replace(temporary, str(self.path))
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    @staticmethod
    def _key(dataset_id, scale):
        return "%s:%s" % (str(dataset_id), str(scale))

    def observe(self, dataset_id, scale, result):
        features = _features(result)
        if features is None:
            return {"status": "insufficient_data", "training_examples": 0,
                    "message": "A série ainda não tem observações suficientes para aprendizagem automática."}
        key = self._key(dataset_id, scale)
        with self._lock:
            model = self._models.setdefault(key, {
                "dataset_id": str(dataset_id), "scale": str(scale), "count": 0,
                "mean": [0.0] * len(features), "m2": [0.0] * len(features),
            })
            count_before = int(model.get("count", 0))
            score = None
            anomaly = None
            if count_before >= MIN_TRAINING_SAMPLES:
                means = model["mean"]
                m2 = model["m2"]
                z_scores = []
                for index, value in enumerate(features):
                    variance = m2[index] / max(1, count_before - 1)
                    deviation = math.sqrt(max(variance, 1e-8))
                    z_scores.append((value - means[index]) / deviation)
                score = math.sqrt(sum(z * z for z in z_scores) / len(z_scores))
                anomaly = bool(score >= ANOMALY_THRESHOLD)

            # Welford update: this observation becomes part of future training only.
            count = count_before + 1
            for index, value in enumerate(features):
                delta = value - model["mean"][index]
                model["mean"][index] += delta / count
                model["m2"][index] += delta * (value - model["mean"][index])
            model["count"] = count
            self._save()

        ready = count >= MIN_TRAINING_SAMPLES
        if not ready:
            message = "A aprender: são necessários pelo menos %d resultados reais; existem %d." % (
                MIN_TRAINING_SAMPLES, count)
        elif anomaly:
            message = "Esta assinatura difere do padrão aprendido. Verifica dados, cobertura e contexto regional."
        else:
            message = "A assinatura está dentro do padrão observado até agora para este produto e escala."
        return {
            "status": "ready" if ready else "learning",
            "training_examples": count,
            "minimum_training_examples": MIN_TRAINING_SAMPLES,
            "anomaly_score": round(score, 4) if score is not None else None,
            "is_unusual": anomaly,
            "threshold": ANOMALY_THRESHOLD if ready else None,
            "message": message,
            "features": ["variabilidade relativa", "declive relativo", "fração em falta", "valor-p"],
            "scope": "produto de dados e escala temporal; compara análises anteriores, não prevê o futuro",
        }

    def status(self):
        with self._lock:
            items = []
            for model in self._models.values():
                count = int(model.get("count", 0))
                items.append({
                    "dataset_id": model.get("dataset_id"),
                    "scale": model.get("scale"),
                    "training_examples": count,
                    "minimum_training_examples": MIN_TRAINING_SAMPLES,
                    "status": "ready" if count >= MIN_TRAINING_SAMPLES else "learning",
                })
            return {"status": "ok", "model_type": "online_unsupervised_anomaly_baseline",
                    "models": items, "model_count": len(items),
                    "persistence": "JSON no diretório de dados do servidor"}
