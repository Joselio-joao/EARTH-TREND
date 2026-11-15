"""Carregador NASA Earth Engine para séries regionais mensais.

A configuração de cada produto fica em datasets.json. O serviço devolve séries
regionais; não afirma produzir raster nem mapas quando a fonte é Series.
As credenciais Earth Engine permanecem exclusivamente no backend.
"""
import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from ..errors import ApiError
from .containers import Series
from .sources import FileLoader


_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE_MAX_ENTRIES = 48
_SERIES_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_LOG = logging.getLogger("earthtrend.earth_engine")
_AUTH_RETRY_SECONDS = 60


class EarthEngineLoader:
    def __init__(self, raw_dir, regions_dir, project_id=None, service_account_json=None):
        self.files = FileLoader(raw_dir)
        self.regions_dir = Path(regions_dir)
        self.project_id = (project_id or "").strip()
        self.service_account_json = service_account_json
        self._ee = None
        self._init_error_at = 0.0
        self._lock = threading.Lock()

    @property
    def configured(self):
        return bool(self.project_id and self.service_account_json)

    def available(self, dataset):
        result = self.files.available(dataset)
        result["earth_engine"] = bool(self.configured and dataset.get("earth_engine"))
        return result

    def _client(self):
        if self._ee is not None:
            return self._ee
        if self._init_error_at and time.monotonic() - self._init_error_at < _AUTH_RETRY_SECONDS:
            raise ApiError(503, "earth_engine_auth_failed",
                           "A autenticação do Earth Engine falhou recentemente. O servidor tentará novamente em breve.")
        if not self.configured:
            raise ApiError(409, "earth_engine_not_configured",
                           "O Google Earth Engine ainda não está autenticado no servidor.")
        with self._lock:
            if self._ee is not None:
                return self._ee
            if self._init_error_at and time.monotonic() - self._init_error_at < _AUTH_RETRY_SECONDS:
                raise ApiError(503, "earth_engine_auth_failed",
                               "A autenticação do Earth Engine falhou recentemente. O servidor tentará novamente em breve.")
            try:
                import ee
                from google.oauth2 import service_account

                # Limita pedidos síncronos getInfo() e chamadas do cliente EE a 90 s.
                # A interface espera 95 s, dando margem para devolver um erro claro.
                ee.data.setDeadline(90_000)

                info = json.loads(self.service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/earthengine",
                            "https://www.googleapis.com/auth/cloud-platform"],
                )
                ee.Initialize(credentials, project=self.project_id)
                self._ee = ee
                return ee
            except Exception as exc:
                self._init_error_at = time.monotonic()
                _LOG.exception("Falha ao autenticar no Earth Engine")
                raise ApiError(
                    503, "earth_engine_auth_failed",
                    "Não foi possível autenticar no Earth Engine. Confirme o projecto, a API e as permissões da conta de serviço."
                ) from exc

    def _geometry(self, ee, region):
        bbox = region["bbox"]
        if region.get("id") == "custom" or not region.get("id"):
            return ee.Geometry.Rectangle(
                [bbox["lon_min"], bbox["lat_min"], bbox["lon_max"], bbox["lat_max"]],
                proj="EPSG:4326", geodesic=False
            )

        path = self.regions_dir / (str(region["id"]) + ".geojson")
        if not path.is_file():
            raise ApiError(422, "earth_engine_boundary_missing",
                           "O contorno GeoJSON de %s não está disponível no servidor." % region["name"])
        try:
            with open(path, encoding="utf-8") as handle:
                obj = json.load(handle)
            kind = obj.get("type")
            if kind == "FeatureCollection":
                geometries = [f.get("geometry") for f in obj.get("features", []) if f.get("geometry")]
            elif kind == "Feature":
                geometries = [obj.get("geometry")]
            elif kind == "GeometryCollection":
                geometries = obj.get("geometries", [])
            else:
                geometries = [obj]
            if not geometries:
                raise ValueError("GeoJSON sem geometrias")
            features = [ee.Feature(ee.Geometry(g, proj="EPSG:4326", geodesic=False))
                        for g in geometries]
            return ee.FeatureCollection(features).geometry()
        except Exception as exc:
            raise ApiError(422, "earth_engine_boundary_invalid",
                           "Não foi possível interpretar o GeoJSON de %s: %s" %
                           (path.name, str(exc)[:250])) from exc

    @staticmethod
    def _spec(dataset):
        spec = dataset.get("earth_engine")
        if not isinstance(spec, dict) or not spec.get("collection") or not spec.get("band"):
            return None
        return spec

    def _cache_key(self, dataset, region, start, end, spec):
        boundary_version = None
        region_id = region.get("id")
        if region_id and region_id not in ("custom",):
            path = self.regions_dir / (str(region_id) + ".geojson")
            try:
                stat = path.stat()
                boundary_version = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                boundary_version = None
        payload = {
            "dataset": dataset.get("id"),
            "spec": spec,
            "region": region_id,
            "bbox": region.get("bbox"),
            "boundary_version": boundary_version,
            "start": start,
            "end": end,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cached_rows(self, key):
        now = time.monotonic()
        with _CACHE_LOCK:
            entry = _SERIES_CACHE.get(key)
            if entry is None:
                return None
            expires_at, rows = entry
            if expires_at <= now:
                del _SERIES_CACHE[key]
                return None
            _SERIES_CACHE.move_to_end(key)
            return list(rows)

    def _store_rows(self, key, rows):
        with _CACHE_LOCK:
            _SERIES_CACHE[key] = (time.monotonic() + _CACHE_TTL_SECONDS, tuple(rows))
            _SERIES_CACHE.move_to_end(key)
            while len(_SERIES_CACHE) > _CACHE_MAX_ENTRIES:
                _SERIES_CACHE.popitem(last=False)

    def _to_series(self, rows, dataset, spec, cache_hit=False):
        return Series(
            ym=[row[0] for row in rows],
            values=np.asarray([row[1] for row in rows], dtype=float),
            unit=dataset.get("native_unit"),
            files=[],
            meta={
                "source": "Google Earth Engine",
                "collection": spec["collection"],
                "band": spec["band"],
                "cloud_project": self.project_id,
                "aggregation": spec.get("aggregation", "Média espacial mensal sobre o polígono da região"),
                "temporal_aggregation": spec.get("temporal_aggregation", "média mensal das imagens disponíveis"),
                "scale_m": str(spec.get("scale_m")),
                "quality_filter": spec.get("quality_filter", "não configurado"),
                "cache": "memória local; validade máxima de 6 horas" if cache_hit else "miss",
                "note": "Série regional; este carregador ainda não devolve um raster para mapas.",
            },
            masked_invalid=0,
        )

    def _prepared_collection(self, ee, spec, start_date, end_date):
        collection = (ee.ImageCollection(spec["collection"])
                      .filterDate(start_date, end_date)
                      .select([spec["band"]] + ([spec["qa_band"]] if spec.get("qa_band") else [])))

        def prepare(image):
            image = ee.Image(image)
            band = image.select(spec["band"])
            if spec.get("qa_band"):
                qa = image.select(spec["qa_band"])
                band = band.updateMask(qa.eq(int(spec.get("qa_value", 0))))
            scale = float(spec.get("value_scale", 1.0))
            if scale != 1.0:
                band = band.multiply(scale)
            offset = float(spec.get("value_offset", 0.0))
            if offset != 0.0:
                band = band.add(offset)
            return band.copyProperties(image, ["system:time_start"])

        return collection.map(prepare).select(spec["band"])

    def load(self, dataset, region, start, end):
        # Ficheiros locais mantêm prioridade e podem fornecer cubos raster completos.
        local = self.files.available(dataset)
        if local["grid_files"] or local["series_files"]:
            return self.files.load(dataset, region, start, end)

        spec = self._spec(dataset)
        if not spec:
            return self.files.load(dataset, region, start, end)

        cache_key = self._cache_key(dataset, region, start, end, spec)
        cached_rows = self._cached_rows(cache_key)
        if cached_rows is not None:
            return self._to_series(cached_rows, dataset, spec, cache_hit=True)

        ee = self._client()
        geometry = self._geometry(ee, region)
        start_date = "%04d-%02d-01" % (start[0], start[1])
        month_count = (end[0] - start[0]) * 12 + end[1] - start[1] + 1

        try:
            collection = self._prepared_collection(
                ee, spec, start_date,
                "%04d-%02d-01" % ((end[0] + 1, 1) if end[1] == 12 else (end[0], end[1] + 1))
            )
            start_ee_date = ee.Date(start_date)
            offsets = ee.List.sequence(0, month_count - 1)

            # Não usar List.map com um reduceRegion por mês: o Earth Engine
            # pode executar essas agregações em paralelo e rejeitar a consulta
            # com "Too many concurrent aggregations". List.iterate encadeia
            # os meses numa única acumulação server-side.
            def append_month(offset, accumulator):
                month_start = start_ee_date.advance(ee.Number(offset), "month")
                month_end = month_start.advance(1, "month")
                monthly = collection.filterDate(month_start, month_end)
                has_images = monthly.size().gt(0)
                value = ee.Algorithms.If(
                    has_images,
                    monthly.mean().reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=geometry,
                        scale=int(spec["scale_m"]),
                        maxPixels=1e13,
                        bestEffort=bool(spec.get("best_effort", False)),
                    ).get(spec["band"]),
                    None,
                )
                record = ee.Dictionary({"timestamp": month_start.millis(), "value": value})
                return ee.List(accumulator).add(record)

            records = ee.List(offsets.iterate(append_month, ee.List([]))).getInfo()
        except Exception as exc:
            detail = str(exc)
            lowered = detail.lower()
            dataset_name = dataset.get("name", dataset.get("id"))
            if "too many concurrent aggregations" in lowered or "quota" in lowered or "rate limit" in lowered:
                raise ApiError(429, "earth_engine_busy",
                               "O serviço de dados está temporariamente sobrecarregado ao processar %s. "
                               "Aguarde um pouco e tente novamente com um período menor." % dataset_name) from exc
            if "deadline" in lowered or "timed out" in lowered or "timeout" in lowered:
                raise ApiError(504, "earth_engine_timeout",
                               "A consulta de %s demorou mais do que o limite do serviço. "
                               "Reduza o período ou a região e tente novamente." % dataset_name) from exc
            _LOG.exception("Falha na consulta Earth Engine: dataset=%s", dataset_name)
            raise ApiError(502, "earth_engine_query_failed",
                           "O Earth Engine não conseguiu calcular a série mensal de %s. "
                           "Verifique a disponibilidade do produto e tente novamente. "
                           "Os detalhes técnicos foram registados no servidor." % dataset_name) from exc

        rows = []
        for record in records or []:
            timestamp, value = record.get("timestamp"), record.get("value")
            if timestamp is None or value is None:
                continue
            dt = datetime.fromtimestamp(float(timestamp) / 1000.0, tz=timezone.utc)
            rows.append(((dt.year, dt.month), float(value)))
        rows.sort(key=lambda item: item[0])
        if not rows:
            raise ApiError(422, "earth_engine_no_data",
                           "O Earth Engine não devolveu observações para esta região e período.")

        self._store_rows(cache_key, rows)
        return self._to_series(rows, dataset, spec)


    def render_map_png(self, dataset, region, start, end, dimensions=1000):
        """Renderiza um raster temporal real do Earth Engine como PNG para pré-visualização."""
        spec = self._spec(dataset)
        if not spec:
            raise ApiError(409, "map_not_supported",
                           "Este conjunto de dados ainda não tem uma camada raster Earth Engine configurada.")
        visualization = spec.get("visualization")
        if not isinstance(visualization, dict):
            raise ApiError(409, "map_style_missing",
                           "Este produto ainda não tem uma escala cartográfica documentada.")
        ee = self._client()
        geometry = self._geometry(ee, region)
        start_date = "%04d-%02d-01" % (start[0], start[1])
        end_month = (end[0] + 1, 1) if end[1] == 12 else (end[0], end[1] + 1)
        end_date = "%04d-%02d-01" % end_month
        try:
            collection = self._prepared_collection(ee, spec, start_date, end_date)
            image = collection.mean().select(spec["band"]).clip(geometry)
            rendered = image.visualize(
                min=float(visualization["min"]),
                max=float(visualization["max"]),
                palette=list(visualization["palette"]),
            )
            boundary = ee.Image().byte().paint(geometry, 1, 2).visualize(palette=["#172b24"])
            rendered = rendered.blend(boundary)
            thumb_url = rendered.getThumbURL({
                "region": geometry,
                "dimensions": int(dimensions),
                "format": "png",
            })
            request = Request(thumb_url, headers={"User-Agent": "EarthTrendAI/1.0"})
            with urlopen(request, timeout=75) as response:
                content_type = response.headers.get("Content-Type", "")
                if "image/png" not in content_type:
                    raise ValueError("Earth Engine não devolveu uma imagem PNG.")
                image_bytes = response.read(8 * 1024 * 1024 + 1)
            if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
                raise ValueError("A imagem cartográfica está vazia ou excede o limite de 8 MB.")
            return image_bytes
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(502, "earth_engine_map_failed",
                           "Não foi possível gerar o raster de %s: %s" %
                           (dataset.get("name", dataset.get("id")), str(exc)[:300])) from exc
