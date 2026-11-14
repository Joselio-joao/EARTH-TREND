"""Catálogo de datasets e regiões (JSON em app/data) e contornos opcionais em data/regions/<id>.geojson."""
import json
import unicodedata
from pathlib import Path

from ..analysis import grid
from ..errors import ApiError

PUBLIC_DATASET_KEYS = (
    "id", "name", "family", "variable_id", "variable_label", "status", "provider", "version",
    "product_short_name", "product_url", "doi", "citation", "license", "value_kind", "native_unit",
    "resolution", "spatial_resolution_deg", "coverage_note", "limitations", "to_confirm", "note",
)


def _norm(text):
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return " ".join(t.lower().replace("_", " ").replace("-", " ").split())


class Registry:
    def __init__(self, datasets, regions, regions_dir):
        self.datasets = list(datasets)
        self.regions = list(regions)
        self.regions_dir = Path(regions_dir)

    @classmethod
    def load(cls, config_dir, regions_dir):
        base = Path(config_dir)
        with open(base / "datasets.json", encoding="utf-8") as fh:
            datasets = json.load(fh)["datasets"]
        with open(base / "regions.json", encoding="utf-8") as fh:
            regions = json.load(fh)["regions"]
        return cls(datasets, regions, regions_dir)

    # ---------------------------------------------------------------- datasets

    def dataset(self, key):
        k = _norm(key)
        for d in self.datasets:
            if _norm(d["id"]) == k:
                return d
        raise ApiError(404, "dataset_not_found", "Dataset desconhecido: %r. Veja GET /datasets." % (key,))

    @staticmethod
    def public_dataset(d):
        return {k: d[k] for k in PUBLIC_DATASET_KEYS if k in d}

    # ----------------------------------------------------------------- regiões

    def _entry(self, key):
        k = _norm(key)
        for r in self.regions:
            names = [r["id"], r["name"]] + list(r.get("aliases", []))
            if k in [_norm(n) for n in names]:
                return r
        raise ApiError(404, "region_not_found", "Região desconhecida: %r. Veja GET /regions." % (key,))

    def _boundary_path(self, region_id):
        return self.regions_dir / ("%s.geojson" % region_id)

    def _read_rings(self, region_id):
        path = self._boundary_path(region_id)
        if not path.is_file():
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                rings = grid.rings_from_geojson(json.load(fh))
        except (OSError, ValueError) as exc:
            raise ApiError(500, "bad_region_file", "Não foi possível ler %s: %s" % (path.name, exc))
        if not rings:
            raise ApiError(500, "bad_region_file", "%s não tem polígonos (Polygon ou MultiPolygon)." % path.name)
        return rings

    def list_regions(self):
        out = []
        for r in self.regions:
            entry = {"id": r["id"], "name": r["name"], "note": r.get("note")}
            try:
                rings = self._read_rings(r["id"])
            except ApiError as exc:
                entry.update(boundary="invalid", ready=False, approximate=False, bbox=r.get("bbox"),
                             note=exc.message)
                out.append(entry)
                continue
            if rings:
                entry.update(boundary="polygon", ready=True, approximate=False, bbox=grid.rings_bbox(rings))
            elif r.get("bbox"):
                entry.update(boundary="bbox", ready=True, approximate=True, bbox=r["bbox"])
            else:
                entry.update(boundary="missing", ready=False, approximate=False, bbox=None)
            out.append(entry)
        return out

    def resolve_region(self, region_id=None, bbox=None):
        """Devolve {id, name, bbox, rings, boundary, approximate, note}. O contorno oficial tem prioridade."""
        if bbox is not None:
            box = {k: float(bbox[k]) for k in ("lat_min", "lat_max", "lon_min", "lon_max")}
            return {"id": "custom", "name": "Caixa personalizada", "bbox": box, "rings": None,
                    "boundary": "custom", "approximate": False, "note": None}
        r = self._entry(region_id)
        rings = self._read_rings(r["id"])
        if rings:
            return {"id": r["id"], "name": r["name"], "bbox": grid.rings_bbox(rings), "rings": rings,
                    "boundary": "polygon", "approximate": False, "note": r.get("note")}
        if r.get("bbox"):
            return {"id": r["id"], "name": r["name"], "bbox": dict(r["bbox"]), "rings": None,
                    "boundary": "bbox", "approximate": True, "note": r.get("note")}
        raise ApiError(422, "region_needs_boundary",
                       "A região %r precisa do contorno oficial em data/regions/%s.geojson (ver data/README.md)."
                       % (r["name"], r["id"]))
