from __future__ import annotations

from html import escape

from app.results import StoredResult


def _number(value: object, decimals: int = 4) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"
    return escape(str(value))


def render_report(result: StoredResult) -> str:
    payload = result.payload
    origin_label = "Dados científicos" if payload.get("data_origin") == "scientific_dataset" else "Dados sintéticos de teste"
    limitations = "".join(f"<li>{escape(str(item))}</li>" for item in payload.get("limitations", []))
    warnings = "".join(f"<li>{escape(str(item))}</li>" for item in payload.get("validation_warnings", []))
    warning_block = f"<h2>Avisos de validação</h2><ul>{warnings}</ul>" if warnings else ""
    return f"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório EarthTrend AI — {escape(str(payload.get('investigation_id', result.result_id)))}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 20px;color:#17231d;line-height:1.55}}
header{{border-bottom:3px solid #5c9a72;padding-bottom:18px;margin-bottom:28px}}
h1{{font-size:30px;margin:8px 0}}h2{{font-size:18px;margin-top:28px;border-bottom:1px solid #dbe5dd;padding-bottom:6px}}
.meta,.note{{background:#f0f7f1;border:1px solid #d7e8da;border-radius:10px;padding:14px;margin:14px 0}}
dl{{display:grid;grid-template-columns:220px 1fr;gap:7px 18px}}dt{{font-weight:bold;color:#557260}}dd{{margin:0}}
li{{margin:6px 0}}footer{{margin-top:40px;font-size:12px;color:#63736a;border-top:1px solid #dbe5dd;padding-top:16px}}
@media(max-width:600px){{dl{{display:block}}dt{{margin-top:10px}}}}
</style></head>
<body>
<header><div>EARTH TREND AI</div><h1>Relatório de investigação ambiental</h1><div>ID do resultado: {escape(result.result_id)}</div></header>
<section class="meta"><strong>Origem:</strong> {escape(origin_label)}<br><strong>Gerado em:</strong> {escape(result.created_at.isoformat())}</section>
<h2>Configuração</h2><dl>
<dt>Investigação</dt><dd>{escape(str(payload.get('investigation_id', '—')))}</dd>
<dt>Variável</dt><dd>{escape(str(payload.get('variable', 'não especificada')))}</dd>
<dt>Unidade</dt><dd>{escape(str(payload.get('unit', 'não declarada')))}</dd>
<dt>Ficheiro</dt><dd>{escape(str(payload.get('filename', 'série fornecida')))}</dd>
<dt>Observações</dt><dd>{escape(str(payload.get('n_observations', '—')))}</dd>
</dl>
<h2>Metodologia</h2><p>A série temporal foi ordenada por data. A análise combina regressão linear, coeficiente R², inclinação de Sen e teste de Mann–Kendall. Os resultados descrevem uma tendência estatística e não demonstram causalidade.</p>
<h2>Resultados</h2><dl>
<dt>Direção</dt><dd>{escape(str(payload.get('direction', '—')))}</dd>
<dt>Inclinação linear</dt><dd>{_number(payload.get('slope_per_year', '—'))} por ano</dd>
<dt>Inclinação de Sen</dt><dd>{_number(payload.get('sen_slope_per_year', '—'))} por ano</dd>
<dt>R²</dt><dd>{_number(payload.get('r_squared', '—'))}</dd>
<dt>Mann–Kendall S</dt><dd>{escape(str(payload.get('mann_kendall_s', '—')))}</dd>
<dt>Valor p</dt><dd>{_number(payload.get('p_value', '—'))}</dd>
<dt>Significância</dt><dd>{'Sim' if payload.get('statistically_significant') else 'Não detetada'}</dd>
</dl>
<h2>Limitações</h2><ul>{limitations}</ul>
{warning_block}
<footer>EarthTrend AI · Relatório gerado a partir dos dados e resultados registados. Confirmar a fonte, unidades e qualidade antes de utilização formal.</footer>
</body></html>"""
