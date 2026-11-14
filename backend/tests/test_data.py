import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.config import PACKAGE_DATA
from app.data import split_geojson, sources
from app.data.registry import Registry
from app.errors import ApiError

try:
    import xarray  # noqa: F401
    HAVE_XARRAY = True
except ImportError:
    HAVE_XARRAY = False

SQUARE = {"type": "Feature", "properties": {"shapeName": "Luanda"},
          "geometry": {"type": "Polygon", "coordinates": [[[13.0, -9.0], [14.0, -9.0], [14.0, -8.5],
                                                          [13.0, -8.5], [13.0, -9.0]]]}}


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.regions_dir = Path(self.tmp.name) / "regions"
        self.reg = Registry.load(PACKAGE_DATA, self.regions_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shipped_catalogue(self):
        d = self.reg.dataset("GPM_IMERG_monthly")
        self.assertEqual((d["id"], d["status"]), ("gpm_imerg_monthly", "available"))
        self.assertEqual(d["doi"], "10.5067/GPM/IMERG/3B-MONTH/07")
        self.assertEqual(sorted(x["status"] for x in self.reg.datasets), ["available", "planned", "planned", "planned"])
        self.assertIn("citation", self.reg.public_dataset(d))
        self.assertNotIn("file_patterns", self.reg.public_dataset(d))
        with self.assertRaises(ApiError) as ctx:
            self.reg.dataset("nope")
        self.assertEqual(ctx.exception.status, 404)

    def test_installed_angola_boundary_is_official_polygon(self):
        installed = Registry.load(PACKAGE_DATA, Path(__file__).parents[1] / "data" / "regions")
        for key in ("angola", "Angola", "República de Angola"):
            r = installed.resolve_region(key)
            self.assertEqual((r["boundary"], r["approximate"]), ("polygon", False))
        self.assertLess(r["bbox"]["lat_max"], -4.0)
        self.assertGreater(r["bbox"]["lon_min"], 10.0)

    def test_installed_provinces_resolve_to_official_polygons(self):
        installed = Registry.load(PACKAGE_DATA, Path(__file__).parents[1] / "data" / "regions")
        for key in ("luanda", "Luanda, Angola", "Huila", "Huíla, Angola", "Bengo"):
            r = installed.resolve_region(key)
            self.assertEqual((r["boundary"], r["approximate"]), ("polygon", False))

    def test_polygon_file_takes_priority_and_gives_the_bbox(self):
        self.regions_dir.mkdir()
        (self.regions_dir / "luanda.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [SQUARE]}))
        r = self.reg.resolve_region("Luanda")
        self.assertEqual((r["boundary"], r["approximate"]), ("polygon", False))
        self.assertEqual(r["bbox"], {"lat_min": -9.0, "lat_max": -8.5, "lon_min": 13.0, "lon_max": 14.0})
        by_id = {x["id"]: x for x in self.reg.list_regions()}
        self.assertTrue(by_id["luanda"]["ready"] and not by_id["namibe"]["ready"])
        self.assertFalse(by_id["angola"]["approximate"])
        self.assertEqual(by_id["angola"]["boundary"], "missing")
        self.assertEqual(by_id["namibe"]["boundary"], "missing")

    def test_broken_boundary_file_is_reported(self):
        self.regions_dir.mkdir()
        (self.regions_dir / "angola.geojson").write_text("{nao e json")
        with self.assertRaises(ApiError) as ctx:
            self.reg.resolve_region("angola")
        self.assertEqual(ctx.exception.code, "bad_region_file")
        self.assertEqual({x["id"]: x for x in self.reg.list_regions()}["angola"]["boundary"], "invalid")

    def test_custom_box_and_unknown_region(self):
        r = self.reg.resolve_region(bbox={"lat_min": -10, "lat_max": -9, "lon_min": 13, "lon_max": 14})
        self.assertEqual((r["id"], r["boundary"]), ("custom", "custom"))
        with self.assertRaises(ApiError) as ctx:
            self.reg.resolve_region("atlantida")
        self.assertEqual(ctx.exception.status, 404)

    def test_split_geojson_makes_files_the_registry_can_use(self):
        gj = {"type": "FeatureCollection", "features": [
            dict(SQUARE), {"type": "Feature", "properties": {"shapeName": "Huíla"}, "geometry": SQUARE["geometry"]}]}
        written = split_geojson.split(gj, "shapeName", self.regions_dir)
        self.assertEqual([w[0] for w in written], ["luanda", "huila"])
        self.assertEqual(self.reg.resolve_region("Huíla, Angola")["boundary"], "polygon")
        self.assertEqual(split_geojson.slugify("Cuando Cubango"), "cuando_cubango")


class SeriesCsv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, name="angola.csv"):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_reads_giovanni_style_header_units_and_fill_values(self):
        p = self.write("Titulo do ficheiro\nOutra linha de metadados\n# units: mm/day\n# source: Giovanni\n"
                       "time,mean_precipitation\n2015-01-01T00:00:00Z,3.5\n2015-02-01T00:00:00Z,-9999.9\n"
                       "2015-03-01,4.25\n201504,\n")
        s = sources.load_series_csv(p, (2015, 1), (2015, 12))
        self.assertEqual(s.unit, "mm/day")
        self.assertEqual(s.meta, {"source": "Giovanni"})
        self.assertEqual(s.ym, [(2015, 1), (2015, 2), (2015, 3), (2015, 4)])
        self.assertEqual(s.masked_invalid, 1)
        self.assertEqual(s.values[0], 3.5)
        self.assertTrue(np.isnan(s.values[1]) and np.isnan(s.values[3]))

    def test_period_filter(self):
        p = self.write("# units: mm/day\n2014-12,1\n2015-01,2\n2015-02,3\n2015-03,4\n")
        s = sources.load_series_csv(p, (2015, 1), (2015, 2))
        self.assertEqual(s.ym, [(2015, 1), (2015, 2)])

    def test_units_are_never_assumed(self):
        with self.assertRaises(ApiError) as ctx:
            sources.load_series_csv(self.write("2015-01,2\n2015-02,3\n"), (2015, 1), (2015, 12))
        self.assertEqual(ctx.exception.code, "units_missing")
        self.assertIn("# units", ctx.exception.message)

    def test_negative_values_are_masked_when_the_dataset_says_so(self):
        p = self.write("# units: mm/day\n2015-01,2\n2015-02,-3\n")
        s = sources.load_series_csv(p, (2015, 1), (2015, 12), valid_min=0)
        self.assertTrue(np.isnan(s.values[1]))
        self.assertEqual(s.masked_invalid, 1)

    def test_bad_rows_are_errors_not_silently_dropped(self):
        for text, code in (("# units: mm/day\n2015-01,2\n2015-01,3\n", "duplicate_months"),
                           ("# units: mm/day\n2015-01,2\nabril,3\n", "bad_csv"),
                           ("# units: mm/day\n2015-01,abc\n", "bad_csv"),
                           ("# units: mm/day\n2015-01\n", "bad_csv"),
                           ("# units: mm/day\nsó cabeçalho\n", "bad_csv")):
            with self.assertRaises(ApiError, msg=text) as ctx:
                sources.load_series_csv(self.write(text), (2015, 1), (2015, 12))
            self.assertEqual(ctx.exception.code, code, text)

    def test_period_outside_the_file_reports_the_coverage(self):
        with self.assertRaises(ApiError) as ctx:
            sources.load_series_csv(self.write("# units: mm/day\n2015-01,2\n2015-06,3\n"), (2020, 1), (2021, 12))
        self.assertEqual(ctx.exception.code, "no_data_in_period")
        self.assertIn("2015-01 a 2015-06", ctx.exception.message)


class Loader(unittest.TestCase):
    dataset = {"id": "gpm_imerg_monthly", "file_patterns": ["*.nc4", "*.HDF5"], "valid_min": 0}
    region = {"id": "angola", "bbox": {"lat_min": -18, "lat_max": -4, "lon_min": 11, "lon_max": 24}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name)
        self.loader = sources.FileLoader(self.raw)

    def tearDown(self):
        self.tmp.cleanup()

    def test_without_files_the_answer_is_a_clear_409_never_made_up_data(self):
        with self.assertRaises(ApiError) as ctx:
            self.loader.load(self.dataset, self.region, (2015, 1), (2015, 12))
        self.assertEqual((ctx.exception.status, ctx.exception.code), (409, "data_unavailable"))
        self.assertIn("data/raw/gpm_imerg_monthly", ctx.exception.message)
        self.assertEqual(self.loader.available(self.dataset), {"grid_files": 0, "series_files": 0})

    def test_grid_files_are_found_by_pattern(self):
        folder = self.raw / "gpm_imerg_monthly"
        folder.mkdir()
        for n in ("b.nc4", "a.HDF5", "ignorar.txt"):
            (folder / n).write_text("x")
        names = [Path(p).name for p in self.loader.grid_files(self.dataset)]
        self.assertEqual(names, ["a.HDF5", "b.nc4"])
        self.assertEqual(self.loader.available(self.dataset)["grid_files"], 2)

    def test_series_csv_is_the_fallback_when_there_is_no_grid(self):
        folder = self.raw / "gpm_imerg_monthly" / "series"
        folder.mkdir(parents=True)
        (folder / "angola.csv").write_text("# units: mm/day\n2015-01,2\n2015-02,3\n")
        s = self.loader.load(self.dataset, self.region, (2015, 1), (2015, 12))
        self.assertEqual(s.ym, [(2015, 1), (2015, 2)])
        self.assertEqual(self.loader.available(self.dataset)["series_files"], 1)


@unittest.skipUnless(HAVE_XARRAY, "xarray não está instalado")
class CubeFromNetcdf(unittest.TestCase):
    """Cria ficheiros pequenos e SINTÉTICOS só para testar a leitura. Nunca são dados da NASA."""
    dataset = {"id": "teste", "variable": "precipitation", "valid_min": 0}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, year, month, units="mm/day", lat_name="lat", lon_name="lon", fill=False):
        import xarray as xr
        lat = [-10.05, -10.15, -10.25]                    # decrescente, como em muitos produtos
        lon = [14.05, 14.15, 14.25, 14.35]
        data = np.full((1, 4, 3), float(month))            # (time, lon, lat), a ordem do IMERG
        if fill:
            data[0, 0, 0] = -9999.9
        ds = xr.Dataset({"precipitation": (("time", lon_name, lat_name), data, {"units": units})},
                        coords={"time": [np.datetime64("%d-%02d-01" % (year, month))],
                                lon_name: lon, lat_name: lat})
        path = self.dir / ("sintetico_%d%02d.nc" % (year, month))
        ds.to_netcdf(path)
        return str(path)

    def test_subset_sort_units_and_masking(self):
        files = [self.make(2015, 2), self.make(2015, 1, fill=True)]       # fora de ordem de propósito
        bbox = {"lat_min": -10.2, "lat_max": -10.0, "lon_min": 14.0, "lon_max": 14.2}
        cube = sources.load_cube(files, self.dataset, bbox, (2015, 1), (2015, 12))
        self.assertEqual(cube.ym, [(2015, 1), (2015, 2)])
        self.assertEqual(cube.values.shape, (2, 2, 2))
        self.assertTrue(np.all(np.diff(cube.lats) > 0) and np.all(np.diff(cube.lons) > 0))
        self.assertEqual(cube.unit, "mm/day")
        self.assertEqual(cube.masked_invalid, 1)
        self.assertEqual(cube.values[1, 0, 0], 2.0)

    def test_other_coordinate_names_and_period_filter(self):
        files = [self.make(2015, 1, lat_name="latitude", lon_name="longitude"), self.make(2016, 1, lat_name="latitude", lon_name="longitude")]
        bbox = {"lat_min": -11, "lat_max": -10, "lon_min": 14, "lon_max": 15}
        cube = sources.load_cube(files, self.dataset, bbox, (2016, 1), (2016, 12))
        self.assertEqual(cube.ym, [(2016, 1)])

    def test_errors_are_explicit(self):
        bbox = {"lat_min": -11, "lat_max": -10, "lon_min": 14, "lon_max": 15}
        with self.assertRaises(ApiError) as ctx:
            sources.load_cube([self.make(2015, 1)], dict(self.dataset, variable="outra"), bbox, (2015, 1), (2015, 12))
        self.assertEqual(ctx.exception.code, "variable_not_found")
        with self.assertRaises(ApiError) as ctx:
            sources.load_cube([self.make(2015, 1)], self.dataset, bbox, (2020, 1), (2020, 12))
        self.assertEqual(ctx.exception.code, "no_data_in_period")
        far = {"lat_min": 30, "lat_max": 31, "lon_min": 14, "lon_max": 15}
        with self.assertRaises(ApiError) as ctx:
            sources.load_cube([self.make(2015, 1)], self.dataset, far, (2015, 1), (2015, 12))
        self.assertEqual(ctx.exception.code, "region_outside_data")
        one = self.make(2015, 1)
        with self.assertRaises(ApiError) as ctx:
            sources.load_cube([one, one], self.dataset, bbox, (2015, 1), (2015, 12))
        self.assertEqual(ctx.exception.code, "duplicate_months")


if __name__ == "__main__":
    unittest.main()
