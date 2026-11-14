"""Inspeciona um ficheiro NASA (NetCDF/HDF5) antes de o usar: variáveis, dimensões, unidades e período.

Serve para o passo "confirmar a estrutura dos dados" (manual, passo 2.4):

    python -m app.data.describe caminho/ficheiro.nc4
    python -m app.data.describe caminho/ficheiro.HDF5 --group Grid
"""
import argparse
import sys


def describe(path, group=None):
    import xarray as xr

    ds = xr.open_dataset(path, group=group)
    lines = ["Ficheiro: %s%s" % (path, "  (grupo %s)" % group if group else ""),
             "Dimensões: " + ", ".join("%s=%d" % (k, v) for k, v in ds.sizes.items()), "", "Coordenadas:"]
    for name, c in ds.coords.items():
        try:
            span = "%s .. %s" % (c.values.min(), c.values.max())
        except Exception:
            span = "?"
        lines.append("  %-12s %-14s %-12s %s" % (name, c.dtype, tuple(c.shape), span))
    lines += ["", "Variáveis (nome, dimensões, unidades, valor de preenchimento):"]
    candidates = []
    for name, v in ds.data_vars.items():
        units = v.attrs.get("units", "(sem atributo units)")
        fill = v.attrs.get("_FillValue", v.encoding.get("_FillValue", "-"))
        lines.append("  %-28s %-24s %-20s %s" % (name, tuple(v.dims), units, fill))
        if {"lat", "latitude"} & set(v.dims) and {"lon", "longitude"} & set(v.dims):
            candidates.append(name)
    if not ds.data_vars:
        lines.append("  (nenhuma: se for HDF5 do IMERG, tente --group Grid)")
    if candidates:
        lines += ["", "Candidatas para \"variable\" em app/data/datasets.json: " + ", ".join(candidates)]
    if ds.attrs:
        lines += ["", "Atributos globais (primeiros 15):"]
        for k in list(ds.attrs)[:15]:
            lines.append("  %s: %s" % (k, str(ds.attrs[k])[:100]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path")
    ap.add_argument("--group", help="grupo HDF5/NetCDF onde estão as variáveis (ex.: Grid)")
    args = ap.parse_args(argv)
    try:
        print(describe(args.path, args.group))
    except ImportError:
        print("Instale as dependências primeiro: pip install -r requirements.txt", file=sys.stderr)
        return 2
    except Exception as exc:
        print("Não consegui abrir %s: %s\nSe for HDF5 do IMERG, tente: --group Grid" % (args.path, exc),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
