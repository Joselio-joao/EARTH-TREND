"""Carregador opcional GPM IMERG através do Google Earth Engine.

Usa uma conta de serviço no servidor. Nunca colocar a chave no frontend ou no Git.
Quando não há credenciais, o backend continua a aceitar ficheiros locais como antes.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..errors import ApiError
from .containers import Series
from .sources import FileLoader


class EarthEngineLoader:
    COLLECTION = "NASA/GPM_L3/IMERG_MONTHLY_V07"
    BAND = "precipitation"
    SCALE_METRES = 11132

    def __init__(self, raw_dir, regions_dir, project_id=None, service_account_json=None):
        self.files = FileLoader(raw_dir)
        self.regions_dir = Path(regions_dir)
        self.project_id = (project_id or "").strip()
        self.service_account_json = service_account_json
        self._ee = None
        self._init_error = None
        self._lock = threading.Lock()

    @property
    def configured(self):
        return bool(self.project_id and self.service_account_json)

    def available(self, dataset):
        result = self.files.available(dataset)
        result["earth_engine"] = bool(self.configured and dataset.get("id") == "gpm_imerg_monthly")
        return result

    def _client(self):
        if self._ee is not None:
            return self._ee
        if self._init_error:
            raise ApiError(503, "earth_engine_auth_failed", self._init_error)
        if not self.configured:
            raise ApiError(409, "earth_engine_not_configured",
                           "O Google Earth Engine ainda não está autenticado no servidor.")
        with self._lock:
            if self._ee is not None:
                return self._ee
            if self._init_error:
                raise ApiError(503, "earth_engine_auth_failed", self._init_error)
            try:
                import ee
                from google.oauth2 import service_account

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
                self._init_error = (
                    "Não foi possível autenticar no Earth Engine. Confirme o registo do projecto, "
                    "a API activada e as permissões da conta de serviço. Detalhe técnico: %s" % str(exc)[:400]
                )
                raise ApiError(503, "earth_engine_auth_failed", self._init_error) from exc

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
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(422, "earth_engine_boundary_invalid",
                           "Não foi possível interpretar o GeoJSON de %s: %s" %
                           (path.name, str(exc)[:250])) from exc

    def load(self, dataset, region, start, end):
        # Ficheiros locais mantêm prioridade e preservam mapas raster completos.
        local = self.files.available(dataset)
        if local["grid_files"] or local["series_files"]:
            return self.files.load(dataset, region, start, end)
        if dataset.get("id") != "gpm_imerg_monthly":
            return self.files.load(dataset, region, start, end)

        ee = self._client()
        geometry = self._geometry(ee, region)
        start_date = "%04d-%02d-01" % (start[0], start[1])
        end_year, end_month = end
        if end_month == 12:
            end_date = "%04d-01-01" % (end_year + 1)
        else:
            end_date = "%04d-%02d-01" % (end_year, end_month + 1)

        try:
            collection = (ee.ImageCollection(self.COLLECTION)
                          .filterDate(start_date, end_date)
                          .select(self.BAND))

            def add_regional_mean(image):
                mean_value = ee.Image(image).reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=self.SCALE_METRES,
                    maxPixels=1e13,
                    bestEffort=True,
                ).get(self.BAND)
                return ee.Image(image).set("earthtrend_regional_mean", mean_value)

            reduced = collection.map(add_regional_mean).sort("system:time_start")
            dates = reduced.aggregate_array("system:time_start").getInfo()
            values = reduced.aggregate_array("earthtrend_regional_mean").getInfo()
        except Exception as exc:
            raise ApiError(502, "earth_engine_query_failed",
                           "O Earth Engine não conseguiu calcular a série regional: %s" % str(exc)[:400]) from exc

        if not dates or not values or len(dates) != len(values):
            raise ApiError(422, "earth_engine_no_data",
                           "O Earth Engine não devolveu observações para esta região e período.")
        rows = []
        for timestamp, value in zip(dates, values):
            if value is None:
                continue
            dt = datetime.fromtimestamp(float(timestamp) / 1000.0, tz=timezone.utc)
            rows.append(((dt.year, dt.month), float(value)))
        rows.sort(key=lambda item: item[0])
        if not rows:
            raise ApiError(422, "earth_engine_no_data",
                           "Não existem valores válidos de precipitação nesta região e período.")

        return Series(
            ym=[row[0] for row in rows],
            values=np.asarray([row[1] for row in rows], dtype=float),
            unit="mm/hr",
            files=[],
            meta={
                "source": "Google Earth Engine",
                "collection": self.COLLECTION,
                "band": self.BAND,
                "cloud_project": self.project_id,
                "aggregation": "Média espacial da banda precipitation sobre o polígono da região",
                "scale_m": str(self.SCALE_METRES),
                "note": "Série regional calculada no Earth Engine; este modo ainda não fornece raster para mapas.",
            },
            masked_invalid=0,
        )
