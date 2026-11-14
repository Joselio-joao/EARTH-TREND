"""Divide um GeoJSON de províncias (várias features) em data/regions/<id>.geojson, um por região.

    python -m app.data.split_geojson angola_adm1.geojson --name-field shapeName --out ../data/regions

O nome de cada feature vira o id: "Huíla" -> huila.geojson. Os ids têm de coincidir com os de
app/data/regions.json (luanda, namibe, huila...). Contornos de fontes abertas, como o geoBoundaries
ou o Natural Earth: confirme a licença e cite a fonte.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


def slugify(name):
    t = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def split(geojson, name_field, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for feature in geojson.get("features", []):
        name = (feature.get("properties") or {}).get(name_field)
        if not name:
            continue
        slug = slugify(name)
        doc = {"type": "FeatureCollection", "features": [feature]}
        (out / ("%s.geojson" % slug)).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        written.append((slug, str(name)))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("geojson")
    ap.add_argument("--name-field", default="shapeName", help="propriedade com o nome (geoBoundaries: shapeName)")
    ap.add_argument("--out", default="../data/regions")
    args = ap.parse_args(argv)
    try:
        with open(args.geojson, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print("Não consegui ler %s: %s" % (args.geojson, exc), file=sys.stderr)
        return 2
    written = split(doc, args.name_field, args.out)
    if not written:
        print("Nenhuma feature com a propriedade %r. Confirme o nome com --name-field." % args.name_field,
              file=sys.stderr)
        return 1
    for slug, name in written:
        print("%s.geojson  <-  %s" % (slug, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
