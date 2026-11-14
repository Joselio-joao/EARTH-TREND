"""Casos de uso da API, sem depender do FastAPI: validação, carregamento, análise e armazenamento."""
import datetime
import threading

from . import __version__
from .analysis import pipeline, timeops
from .errors import ApiError
from .reports import report as reports

DEFAULT_DATASET = "gpm_imerg_monthly"
MAX_QUESTION = 300


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Service:
    def __init__(self, settings, registry, loader, store):
        self.settings = settings
        self.registry = registry
        self.loader = loader
        self.store = store
        self.slots = threading.BoundedSemaphore(settings.max_concurrent)

    # ------------------------------------------------------------- catálogo

    def health(self):
        return {"status": "ok", "version": __version__, "time": _now()}

    def list_datasets(self):
        out = []
        for d in self.registry.datasets:
            item = self.registry.public_dataset(d)
            if d.get("status") == "available":
                files = self.loader.available(d)
                item.update(files=files, ready=files["grid_files"] + files["series_files"] > 0)
            else:
                item.update(files=None, ready=False)
            out.append(item)
        return out

    def list_regions(self):
        return self.registry.list_regions()

    # ------------------------------------------------------------ validação

    @staticmethod
    def _validate_bbox(bbox):
        try:
            b = {k: float(bbox[k]) for k in ("lat_min", "lat_max", "lon_min", "lon_max")}
        except (KeyError, TypeError, ValueError):
            raise ApiError(422, "invalid_bbox", "bbox precisa de lat_min, lat_max, lon_min e lon_max (números).")
        if not (-90 <= b["lat_min"] < b["lat_max"] <= 90 and -180 <= b["lon_min"] < b["lon_max"] <= 180):
            raise ApiError(422, "invalid_bbox", "bbox inválida: use -90 <= lat_min < lat_max <= 90 e "
                           "-180 <= lon_min < lon_max <= 180.")
        return b

    def _normalize(self, payload):
        dataset = self.registry.dataset(payload.get("dataset_id") or DEFAULT_DATASET)
        if dataset.get("status") != "available":
            raise ApiError(422, "dataset_not_ready", "O dataset %r ainda não está ligado ao backend (estado: %s)."
                           % (dataset["name"], dataset.get("status")))
        region_id, bbox = payload.get("region_id"), payload.get("bbox")
        if bool(region_id) == bool(bbox):
            raise ApiError(422, "invalid_request", "Indique region_id ou bbox (exatamente um dos dois).")
        region = self.registry.resolve_region(region_id=region_id,
                                              bbox=self._validate_bbox(bbox) if bbox else None)
        if not payload.get("start") or not payload.get("end"):
            raise ApiError(422, "invalid_period", "Indique start e end (AAAA, AAAA-MM ou AAAA-MM-DD).")
        try:
            start, end = timeops.parse_period(payload["start"], payload["end"])
        except ValueError as exc:
            raise ApiError(422, "invalid_period", str(exc))

        scale = str(payload.get("scale") or "annual").lower()
        if scale not in timeops.SCALES:
            raise ApiError(422, "invalid_scale", "scale deve ser um de: %s." % ", ".join(timeops.SCALES))
        if scale == "native":
            scale = dataset["resolution"]
        season_months = season_code = None
        if scale == "seasonal":
            try:
                if payload.get("season_months"):
                    season_months = timeops.validate_season_months(payload["season_months"])
                elif payload.get("season"):
                    season_months = timeops.SEASONS[str(payload["season"]).upper()]
                else:
                    raise ValueError("indique season (DJF, MAM, JJA ou SON) ou season_months")
            except KeyError:
                raise ApiError(422, "invalid_season", "season deve ser DJF, MAM, JJA ou SON.")
            except ValueError as exc:
                raise ApiError(422, "invalid_season", str(exc))
            season_code = timeops.season_label(season_months)

        try:
            alpha = float(payload.get("alpha") if payload.get("alpha") is not None else 0.05)
        except (TypeError, ValueError):
            alpha = float("nan")
        if not 0.0 < alpha < 0.5:
            raise ApiError(422, "invalid_alpha", "alpha deve estar entre 0 e 0,5 (por omissão, 0,05).")
        question = payload.get("question")
        question = str(question).strip() if question is not None else None
        if question and len(question) > MAX_QUESTION:
            raise ApiError(422, "invalid_question", "A pergunta pode ter no máximo %d caracteres." % MAX_QUESTION)

        wraps = bool(season_months) and season_months[0] > season_months[-1]
        req = {"dataset_id": dataset["id"], "region_id": region["id"] if region_id else None,
               "bbox": region["bbox"] if bbox else None, "start": start, "end": end,
               "load_start": (start[0] - 1, 1) if wraps else start, "scale": scale,
               "season_months": season_months, "season_label": season_code, "alpha": alpha,
               "question": question or None,
               "include_trend_map": bool(payload.get("include_trend_map", False))}
        return req, dataset, region

    def _check_size(self, dataset, region, req):
        res = dataset.get("spatial_resolution_deg")
        if not res:
            return
        b = region["bbox"]
        cells = ((b["lat_max"] - b["lat_min"]) / res + 1) * ((b["lon_max"] - b["lon_min"]) / res + 1)
        months = timeops.months_between(req["load_start"], req["end"])
        if cells * months > self.settings.max_values:
            raise ApiError(422, "request_too_large",
                           "Pedido demasiado grande: cerca de %.1f milhões de valores (%d células x %d meses; o "
                           "máximo configurado é %.1f milhões). Reduza a região ou o período."
                           % (cells * months / 1e6, cells, months, self.settings.max_values / 1e6))

    # -------------------------------------------------------------- análise

    def analyze(self, payload):
        req, dataset, region = self._normalize(payload)
        self._check_size(dataset, region, req)
        if not self.slots.acquire(blocking=False):
            raise ApiError(429, "busy", "O servidor está a processar outras análises. Tente novamente dentro de "
                           "instantes.")
        try:
            source = self.loader.load(dataset, region, req["load_start"], req["end"])
            result = pipeline.run_analysis(dataset, region, req, source, self.settings.min_years)
        finally:
            self.slots.release()
        rid = self.store.new_id()
        result.update(id=rid, created_at=_now(), backend_version=__version__)
        result["links"] = {
            "self": "/results/%s" % rid, "map": "/results/%s/map" % rid if result.get("map") else None,
            "trend_map": "/results/%s/trend-map" % rid if result.get("trend_map") else None,
            "series_csv": "/results/%s/series.csv" % rid, "report_html": "/report/%s" % rid,
            "report_md": "/report/%s?format=md" % rid,
        }
        self.store.save(result)
        return result

    # ------------------------------------------------------------ resultados

    def get_result(self, rid):
        result = self.store.load(rid)
        if result is None:
            raise ApiError(404, "result_not_found", "Resultado %r não encontrado." % (rid,))
        return result

    def get_map(self, rid):
        m = self.get_result(rid).get("map")
        if not m:
            raise ApiError(404, "map_not_available", "Esta análise não tem mapa (os dados já vinham agregados "
                           "numa série).")
        return m

    def get_trend_map(self, rid):
        trend_map = self.get_result(rid).get("trend_map")
        if not trend_map:
            raise ApiError(404, "trend_map_not_available", "Esta análise não calculou tendências por célula.")
        return trend_map

    def list_results(self, limit=20):
        return self.store.list(limit)

    def report(self, rid, fmt="html"):
        result = self.get_result(rid)
        fmt = str(fmt or "html").lower()
        if fmt == "html":
            return reports.render_html(result), "text/html; charset=utf-8"
        if fmt in ("md", "markdown"):
            return reports.render_markdown(result), "text/markdown; charset=utf-8"
        raise ApiError(422, "invalid_format", "format deve ser html ou md.")

    def series_csv(self, rid):
        return reports.series_csv(self.get_result(rid)), "earthtrend-%s.csv" % rid[:8]
