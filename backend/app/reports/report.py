"""Relatório da análise: HTML imprimível (guardar como PDF no navegador), Markdown e CSV da série.

Todo o texto vindo de fora (a pergunta do utilizador, nomes de ficheiros) passa por html.escape.
"""
import csv
import html
import io
import json

from ..analysis.interpret import fmt_auto, fmt_num, fmt_p

E = html.escape

CSS = """
body{font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#14171c;max-width:880px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem;margin:0 0 .25rem}h2{font-size:1.1rem;margin:1.6rem 0 .5rem;border-bottom:1px solid #e3e6ea;padding-bottom:.25rem}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.35rem .5rem;border-bottom:1px solid #eef0f3;vertical-align:top}
th{width:38%;font-weight:600;color:#3d4652}.badge{display:inline-block;padding:.15rem .6rem;border-radius:999px;background:#eef3ff;color:#2f5bea;font-weight:600}
.muted{color:#5b6470;font-size:.9rem}svg{max-width:100%;height:auto}pre{background:#f6f7f9;padding:.75rem;overflow:auto;font-size:.8rem}
@media print{body{margin:0}a{color:inherit;text-decoration:none}}
"""


# ------------------------------------------------------------- conteúdo comum

def _context_rows(r):
    ds, reg, period = r["dataset"], r["region"], r["period"]
    boundary = {"bbox": " (caixa aproximada)", "custom": " (caixa personalizada)",
                "polygon": " (contorno oficial)"}.get(reg["boundary"], "")
    analyzed = "%s a %s" % (period["analyzed"]["first"], period["analyzed"]["last"])
    if period["clipped"]:
        analyzed += " (pedido: %s a %s)" % (period["requested"]["start"], period["requested"]["end"])
    return [
        ("Pergunta", r["request"].get("question") or "(não indicada)"),
        ("Região", reg["name"] + boundary),
        ("Variável", r["variable"]["label"]),
        ("Período analisado", analyzed),
        ("Agregação", r["scale_label"]),
        ("Unidade", r["unit"]),
        ("Fonte", ", ".join(x for x in (ds["name"], ds.get("version"), ds.get("provider")) if x)),
        ("Método", r["trend"]["method"]),
        ("Nível de significância (α)", fmt_num(r["trend"]["alpha"], 2)),
    ]


def _result_rows(r):
    t = r["trend"]
    rows = [("Direção", t["direction_label"])]
    obs = "%d" % t["n_observations"]
    if t.get("expected_observations"):
        obs += " de %d esperadas" % t["expected_observations"]
    if t["direction"] == "inconclusive":
        return rows + [("Motivo", t["reason"]), ("Observações válidas", obs)]
    mag, mk, ols = t["magnitude"], t["mann_kendall"], t.get("ols")
    rows += [
        ("Magnitude (declive de Sen)", "%s %s" % (fmt_auto(mag["slope_per_year"], True), mag["unit_per_year"])),
        ("Incerteza", "IC de %d%%: %s a %s" % (round(mag["ci_level"] * 100), fmt_auto(mag["ci_low"], True),
                                               fmt_auto(mag["ci_high"], True))),
        ("Variação por década", "%s %s" % (fmt_auto(mag["change_per_decade"], True), mag["unit_per_decade"])),
    ]
    if mag.get("relative_change_per_decade_pct") is not None:
        rows.append(("Variação relativa", "%s%% por década" % fmt_num(mag["relative_change_per_decade_pct"], 1, True)))
    rows += [("Valor-p (Mann-Kendall)", fmt_p(mk["p_value"])),
             ("Estatisticamente significativo", "sim" if t["significant"] else "não"),
             ("Observações", obs)]
    if ols:
        rows.append(("Regressão linear (comparação)", "%s %s por ano; R² = %s"
                     % (fmt_auto(ols["slope_per_year"], True), r["unit"], fmt_num(ols["r2"], 2))))
    return rows


# ----------------------------------------------------------------------- SVG

def _svg_chart(s, width=640, height=260):
    pts = [(t, v) for t, v in zip(s["t"], s["values"]) if v is not None]
    if len(pts) < 2:
        return ""
    line = s.get("trend_line")
    lp = [(t, v) for t, v in zip(s["t"], line) if v is not None] if line else []
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    ys = [p[1] for p in pts] + [p[1] for p in lp]
    y0, y1 = min(ys), max(ys)
    x1 = x1 if x1 > x0 else x0 + 1.0
    y1 = y1 if y1 > y0 else y0 + 1.0
    left, right, top, bottom = 64, 14, 12, 30

    def sx(x):
        return left + (x - x0) / (x1 - x0) * (width - left - right)

    def sy(y):
        return height - bottom - (y - y0) / (y1 - y0) * (height - top - bottom)

    d, pen = [], "M"
    for t, v in zip(s["t"], s["values"]):
        if v is None:
            pen = "M"
            continue
        d.append("%s%.1f %.1f" % (pen, sx(t), sy(v)))
        pen = "L"
    out = [
        '<svg viewBox="0 0 %d %d" role="img" aria-label="Série temporal e linha de tendência" '
        'xmlns="http://www.w3.org/2000/svg">' % (width, height),
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#9aa3ad"/>' % (left, top, left, height - bottom),
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#9aa3ad"/>' % (left, height - bottom, width - right, height - bottom),
        '<text x="%d" y="%.0f" font-size="11" text-anchor="end" fill="#3d4652">%s</text>' % (left - 6, sy(y1) + 4, E(fmt_auto(y1))),
        '<text x="%d" y="%.0f" font-size="11" text-anchor="end" fill="#3d4652">%s</text>' % (left - 6, sy(y0) + 4, E(fmt_auto(y0))),
        '<text x="%d" y="%d" font-size="11" fill="#3d4652">%s</text>' % (left, height - 10, E(str(s["labels"][0]))),
        '<text x="%d" y="%d" font-size="11" text-anchor="end" fill="#3d4652">%s</text>' % (width - right, height - 10, E(str(s["labels"][-1]))),
        '<text x="%d" y="%d" font-size="11" fill="#3d4652">%s</text>' % (left + 6, top + 10, E(s.get("unit") or "")),
        '<path d="%s" fill="none" stroke="#315fe8" stroke-width="2"/>' % " ".join(d),
    ]
    if len(pts) <= 60:
        out += ['<circle cx="%.1f" cy="%.1f" r="2.5" fill="#315fe8"/>' % (sx(t), sy(v)) for t, v in pts]
    if len(lp) >= 2:
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#75b64f" stroke-width="2" '
                   'stroke-dasharray="6 4"/>' % (sx(lp[0][0]), sy(lp[0][1]), sx(lp[-1][0]), sy(lp[-1][1])))
    out.append("</svg>")
    return "".join(out)


def _svg_map(m, width=420):
    lats, lons, vals = m.get("lats") or [], m.get("lons") or [], m.get("values") or []
    if not lats or not lons:
        return ""
    dlat, dlon = (m.get("cell_size_deg") or [None, None])
    dlat, dlon = dlat or 1.0, dlon or 1.0
    lat1, lon0 = max(lats) + dlat / 2.0, min(lons) - dlon / 2.0
    k = width / ((max(lons) + dlon / 2.0) - lon0)
    height = ((lat1 - (min(lats) - dlat / 2.0)) * k)
    lo, hi = m.get("min"), m.get("max")

    def color(v):
        if v is None or lo is None:
            return "#e5e7eb"
        f = 0.5 if hi == lo else (v - lo) / (hi - lo)
        a, b = (232, 240, 250), (8, 48, 107)
        return "rgb(%d,%d,%d)" % tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))

    rects = []
    for j, la in enumerate(lats):
        for i, lon in enumerate(lons):
            rects.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                         % ((lon - dlon / 2.0 - lon0) * k, (lat1 - (la + dlat / 2.0)) * k,
                            dlon * k + 0.5, dlat * k + 0.5, color(vals[j][i])))
    legend = "mín. %s, máx. %s (%s)" % (fmt_auto(lo), fmt_auto(hi), m.get("unit") or "")
    return ('<svg viewBox="0 0 %d %.0f" role="img" aria-label="Mapa da média no período" '
            'xmlns="http://www.w3.org/2000/svg">%s</svg><p class="muted">%s. Norte para cima.</p>'
            % (width, height, "".join(rects), E(legend)))


# ---------------------------------------------------------------------- HTML

def _table(rows):
    return "<table>%s</table>" % "".join("<tr><th>%s</th><td>%s</td></tr>" % (E(a), E(str(b))) for a, b in rows)


def _list(items):
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % E(x) for x in items) if items else "<p class=\"muted\">Nenhum.</p>"


def render_html(r):
    ds, pv = r["dataset"], r["provenance"]
    files = ["%s (modificado em %s)" % (f["name"], f["modified"]) for f in pv.get("files") or []]
    chart = _svg_chart(r["series"])
    body = [
        "<h1>EarthTrend AI, relatório de investigação</h1>",
        '<p class="muted">Gerado em %s &middot; análise %s &middot; backend %s</p>'
        % (E(r["created_at"]), E(r["id"]), E(r["backend_version"])),
        "<h2>Contexto</h2>", _table(_context_rows(r)),
        "<h2>Resultado</h2>", '<p><span class="badge">%s</span></p>' % E(r["trend"]["direction_label"]),
        _table(_result_rows(r)),
        "<h2>Série temporal</h2>", chart or '<p class="muted">Dados insuficientes para o gráfico.</p>',
    ]
    if r.get("map"):
        body += ["<h2>Mapa</h2>", _svg_map(r["map"])]
    body += [
        "<h2>Interpretação</h2>", "<p>%s</p>" % E(r["interpretation"]["summary"]),
        "<p><strong>O que esta análise não prova:</strong></p>", _list(r["interpretation"]["does_not_prove"]),
        "<h2>Avisos</h2>", _list(r["warnings"]),
        "<h2>Limitações</h2>", _list(r["limitations"]),
        "<h2>Fonte e proveniência</h2>",
        _table([("Produto", "%s %s" % (ds.get("product_short_name") or ds["name"], ds.get("version") or "")),
                ("Fornecedor", ds.get("provider") or "n/d"), ("DOI", ds.get("doi") or "n/d"),
                ("Ligação", ds.get("product_url") or "n/d"), ("Licença", ds.get("license") or "n/d"),
                ("Unidade nos dados", pv["unit_in_data"] + ("" if pv["unit_declared_in_data"] else " (do registo)"))]),
        "<p><strong>Citação:</strong> %s</p>" % E(ds.get("citation") or "n/d"),
        "<p><strong>Ficheiros usados:</strong></p>", _list(files),
        '<p class="muted">%s</p>' % E(pv["note"]),
        "<h2>Reprodutibilidade</h2><pre>%s</pre>" % E(json.dumps(r["request"], ensure_ascii=False, indent=2)),
        '<p class="muted">Resultado gerado automaticamente pelo motor estatístico da EarthTrend AI. Descreve '
        "observações e estatística; não estabelece causas.</p>",
    ]
    return ('<!doctype html><html lang="pt"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<title>EarthTrend AI, relatório %s</title><style>%s</style></head><body>%s</body></html>"
            % (E(r["id"][:8]), CSS, "".join(body)))


# ------------------------------------------------------------------ Markdown

def render_markdown(r):
    ds, pv = r["dataset"], r["provenance"]
    lines = ["# EarthTrend AI, relatório de investigação", "",
             "_Gerado em %s, análise %s, backend %s_" % (r["created_at"], r["id"], r["backend_version"]), "",
             "## Contexto", ""]
    lines += ["- **%s:** %s" % row for row in _context_rows(r)]
    lines += ["", "## Resultado", ""] + ["- **%s:** %s" % row for row in _result_rows(r)]
    lines += ["", "## Interpretação", "", r["interpretation"]["summary"], "", "O que esta análise não prova:", ""]
    lines += ["- " + x for x in r["interpretation"]["does_not_prove"]]
    lines += ["", "## Avisos", ""] + (["- " + x for x in r["warnings"]] or ["Nenhum."])
    lines += ["", "## Limitações", ""] + ["- " + x for x in r["limitations"]]
    lines += ["", "## Fonte e proveniência", "",
              "- **Produto:** %s %s" % (ds.get("product_short_name") or ds["name"], ds.get("version") or ""),
              "- **DOI:** %s" % (ds.get("doi") or "n/d"), "- **Citação:** %s" % (ds.get("citation") or "n/d")]
    lines += ["- **Ficheiro:** %s (modificado em %s)" % (f["name"], f["modified"]) for f in pv.get("files") or []]
    lines += ["", "## Reprodutibilidade", "", "```json", json.dumps(r["request"], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------- CSV

def series_csv(r):
    s = r["series"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["periodo", "valor", "unidade", "linha_de_tendencia"])
    line = s.get("trend_line") or [None] * len(s["labels"])
    for label, v, ln in zip(s["labels"], s["values"], line):
        w.writerow([label, "" if v is None else repr(float(v)), s["unit"], "" if ln is None else repr(float(ln))])
    return buf.getvalue()
