# EarthTrend AI, backend

API em FastAPI com um motor estatístico de tendências. Recebe uma região, um período e uma escala temporal,
lê dados da NASA que a equipa descarregou, e devolve a direção, a magnitude (declive de Sen com intervalo
de confiança), a significância (Mann-Kendall), um mapa, a proveniência dos dados e as limitações.

Regra de ouro: **nada é inventado**. Sem dados no servidor a resposta é um erro claro (409), nunca números.

## Arrancar

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra http://127.0.0.1:8000/docs para ver e experimentar todos os endpoints.

## Primeiro, os dados reais

Coloque os ficheiros descarregados em `data/raw/gpm_imerg_monthly/` e confirme-os com
`python -m app.data.describe <ficheiro>`. Passo a passo em [`../data/README.md`](../data/README.md).
`GET /datasets` mostra se o servidor já os encontra (`ready: true`).

## Endpoints

| método e caminho | o que faz |
| --- | --- |
| `GET /health` | o backend está ativo? |
| `GET /datasets` | datasets registados, estado, ficheiros encontrados, citação |
| `GET /regions` | regiões e o tipo de fronteira (`polygon`, `bbox` aproximada ou `missing`) |
| `POST /analyze` | executa a análise, guarda e devolve o resultado completo |
| `GET /results` | últimas análises guardadas |
| `GET /results/{id}` | resultado completo |
| `GET /results/{id}/map` | grelha do mapa (média no período), pronta para o Leaflet |
| `GET /results/{id}/trend-map` | tendências estatísticas célula a célula, para colorir o mapa |
| `GET /results/{id}/series.csv` | série temporal em CSV, para verificar noutra ferramenta |
| `GET /report/{id}?format=html\|md` | relatório (HTML para imprimir ou guardar como PDF; Markdown) |

Erros têm sempre a forma `{"error": {"code", "message", "details"}}`.

## Exemplo

```json
POST /analyze
{
  "dataset_id": "gpm_imerg_monthly",
  "region_id": "angola",
  "start": "2015", "end": "2025",
  "scale": "annual",
  "question": "A precipitação anual em Angola está a mudar?"
}
```

`scale`: `monthly` (Mann-Kendall sazonal sobre os meses), `seasonal` (com `season`: `DJF`, `MAM`, `JJA`, `SON`,
ou `season_months`, por exemplo `[10,11,12,1,2,3,4]`), `annual` ou `native`.
Em vez de `region_id` pode enviar `bbox`: `{"lat_min","lat_max","lon_min","lon_max"}`.
Para pedir o mapa estatístico por célula, envie `include_trend_map: true`. O cálculo é opcional para manter o pedido
normal mais leve; a grelha é reduzida a no máximo 40 células por lado e devolve direção, declive de Sen, valor-p,
significância e número de observações por célula.

Partes principais da resposta: `trend` (`direction`, `significant`, `mann_kendall`, `magnitude`, `ols`),
`series` (`labels`, `values`, `trend_line`), `map`, `interpretation`, `data_quality`, `provenance`,
`warnings`, `limitations`. Os campos sem dados a sustentá-los vêm a `null`.

## Como o resultado é calculado

1. Lê só a região e o período pedidos (NetCDF/HDF5 com xarray, ou um CSV já agregado).
2. Confere as unidades pelo atributo `units` do ficheiro. Unidade desconhecida: recusa (422).
3. Converte taxa média do mês em total do mês (mm/dia ou mm/h vezes os dias reais do mês).
4. Agrega em meses, épocas ou anos. Janelas com meses em falta são excluídas, nunca preenchidas.
5. Média espacial ponderada por cos(latitude), só nas células da região (caixa ou contorno oficial).
6. Mann-Kendall com correção de empates (sazonal na escala mensal), declive de Sen com intervalo de
   confiança (Gilbert, 1987) e regressão linear só para comparação. Menos de 10 anos com dados: inconclusivo.
7. Avisos de qualidade: dados em falta, série curta, valores repetidos, autocorrelação dos resíduos.

## Testes

```bash
python -m unittest discover -s tests -v        # não precisa de pytest
```

Os testes do motor, dos dados, do pipeline e do serviço usam apenas numpy e scipy. Os de HTTP
(`tests/test_api.py`) e os de leitura de NetCDF (`tests/test_data.py`) correm quando `fastapi`, `httpx`
e `xarray` estão instalados (`pip install -r requirements-dev.txt`). Os dados dos testes são sintéticos e
nunca saem dos testes.

## Publicar

Comando de arranque: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, com a pasta `backend` como raiz.
Defina `EARTHTREND_ALLOWED_ORIGINS` (o endereço do site) e `EARTHTREND_DATA_DIR` (onde estão os dados);
ver `.env.example`. Confirmem os limites de memória e de disco do serviço escolhido antes da demonstração.
