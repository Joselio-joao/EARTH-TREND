# Backend da EarthTrend AI: reconhecimento, arquitetura e verificações

Documento no formato do pack replica-skill (recon, architect, backend). Data: 2026-11-10.
Guia de uso: [`backend/README.md`](../backend/README.md). Plano de testes: [`test-plan.md`](test-plan.md).

## 1. Estado

| parte | estado |
| --- | --- |
| Motor estatístico (Mann-Kendall, sazonal, Sen com IC, regressão) | feito e testado |
| Agregação, unidades, médias por área, contornos, mapa | feito e testado |
| Leitura de CSV (Giovanni) | feito e testado |
| Leitura de NetCDF/HDF5 (xarray) | escrito e com testes; **não executado** com ficheiros reais |
| API FastAPI e relatório HTML/Markdown/CSV | escritos; lógica testada; o servidor HTTP em si **ainda não foi arrancado** |
| Dados reais da NASA | **não descarregados** (exigem a conta Earthdata da equipa) |
| MODIS, GISTEMP, GLDAS | registados como `planned`; o `/analyze` recusa-os com 422 |

## 2. Reconhecimento (replica-recon)

Regra seguida: reconstruir **funções**, sem copiar código de terceiros. Fontes públicas lidas em 2026-11-10.

| # | fonte | para que serviu |
| --- | --- | --- |
| 1 | Catálogo do produto GPM IMERG Final mensal V07 (GES DISC, via data.nasa.gov e registry.opendata.aws) | nome do produto, DOI, resolução, citação, licença, limitações |
| 2 | Descrição do produto no NCAR RDA (data.ucar.edu) | a variável `precipitation` do V07 mensal é a taxa média mensal em **mm/dia** |
| 3 | NASA Giovanni, Time Series Area-Averaged (gpm.nasa.gov, forum.earthdata.nasa.gov) | funcionalidade de referência e formato de exportação em CSV |
| 4 | O frontend do repositório (`trend-lab.html`, `data-library.html`, `frontend/src/main.tsx`) | regiões, variáveis, períodos e escalas que a interface oferece |

**Ciclo central:** escolher região, variável e período, e obter a direção, magnitude e significância da
tendência, com proveniência e limitações.

### Ecrãs do frontend e o que o backend serve

| ecrã | endpoint |
| --- | --- |
| Biblioteca de dados | `GET /datasets` (nome, fornecedor, versão, DOI, citação, limitações, `ready`) |
| Trend Lab, listas de regiões | `GET /regions` |
| Trend Lab, executar | `POST /analyze` |
| Resultado (gráfico, números) | `trend`, `series`, `interpretation`, `warnings`, `limitations` |
| Mapa | `map` (ou `GET /results/{id}/map`) |
| Exportar relatório | `GET /report/{id}?format=md` ou `html`; dados em `series.csv` |

### Correspondência com as opções da interface

| na interface | no pedido |
| --- | --- |
| Região: Angola, Luanda, Namibe, Huíla, África Austral, Global | `region_id`: `angola`, `luanda`, `namibe`, `huila`, `africa_austral`, `global` (o `/regions` devolve os ids; também aceita o nome) |
| Variável: Precipitação | `dataset_id`: `gpm_imerg_monthly` (a única ligada) |
| Período 2015–2025 | `start: "2015"`, `end: "2025"` |
| Agregação: Mensal, Sazonal, Anual | `scale`: `monthly`, `seasonal` (+ `season`), `annual` |

Pontos a rever na interface:

- **1991–2025** está fora do registo do IMERG (começa em junho de 2000): o resultado vem com `period.clipped: true`
  e um aviso. Para séries mais longas é preciso outro produto.
- **Temperatura**: o protótipo usa GISTEMP (anomalia da temperatura do ar à superfície, resolução grosseira) mas o
  Trend Lab diz "land surface temperature" (que seria MODIS LST). São produtos diferentes: escolham um e usem o nome certo.
- Os números do protótipo (`assets/app.js`, `main.tsx`) são demonstrativos. Quando ligarem o `fetch`, mostrem
  `trend.direction_label`, `trend.magnitude`, `trend.mann_kendall.p_value`, `trend.n_observations` e as listas
  `warnings` e `limitations`. Campos a `null` significam "não calculado".

### Matriz de funcionalidades

| funcionalidade | prioridade | estado |
| --- | --- | --- |
| Série temporal da região a partir dos dados NASA | must | feito (grelha ou CSV) |
| Tendência: direção, magnitude, p, IC | must | feito |
| Escalas mensal, sazonal, anual | must | feito |
| Mapa da média no período | must | feito (grelha) |
| Proveniência, citação, limitações | must | feito |
| Relatório exportável | should | feito (HTML, Markdown, CSV) |
| Tendência célula a célula (mapa de tendências) | should | feito: `include_trend_map` + `/results/{id}/trend-map` |
| Outros datasets (MODIS, GISTEMP, GLDAS) | could | por fazer |
| Contornos das províncias | should | suporte feito; faltam os ficheiros (`data/README.md`) |
| Explicação por IA | could | fora do MVP; há explicação por regras em `interpretation` |

## 3. Arquitetura (replica-architect)

Sem base de dados no MVP: cada análise fica em `data/results/<id>.json`. Stack: Python, FastAPI, numpy, scipy,
xarray. Sem microserviços.

```
backend/app/
  main.py              cria a app (CORS, erros)           api/        rotas e esquemas (finos)
  service.py           validação e casos de uso           analysis/   trend, timeops, grid, pipeline, interpret
  storage.py           resultados em JSON                 data/       catálogo, regiões, leitura, ferramentas
  config.py, errors.py                                    reports/    HTML, Markdown, CSV
```

### API

| método e caminho | quem | entrada | saída |
| --- | --- | --- | --- |
| `GET /health` | todos | n/a | estado e versão |
| `GET /datasets` | todos | n/a | datasets e `ready` |
| `GET /regions` | todos | n/a | regiões, `boundary`, `ready` |
| `POST /analyze` | todos | `AnalysisRequest` | resultado completo com `id` |
| `GET /results`, `/results/{id}`, `/results/{id}/map`, `/results/{id}/series.csv` | todos | id de 32 hex | resultado, mapa, CSV |
| `GET /report/{id}` | todos | `format=html\|md` | relatório |

Só fontes oficiais e públicas, com os ficheiros que a equipa descarregou com a sua conta. O backend nunca chama
endpoints privados de outras aplicações.

### As partes que mordem

- **Taxa não é total.** O V07 mensal vem em taxa média; o backend multiplica pelos dias reais do mês e só aceita
  unidades que reconhece. Nunca assume unidades.
- **Sazonalidade.** A chuva em Angola tem ciclo anual forte. A escala mensal usa Mann-Kendall sazonal; a anual e a
  sazonal agregam primeiro. Janelas com meses em falta são excluídas.
- **Constelação de satélites.** O IMERG muda de sensores ao longo do tempo, o que pode criar artefactos de tendência.
  Vai em `limitations`.
- **Caixas incluem oceano.** Angola sem contorno é uma caixa aproximada. O resultado avisa.
- **Memória.** Um pedido grande é recusado antes de ler (`EARTHTREND_MAX_VALUES`), e só correm 2 análises em paralelo.
- **Fusos e datas.** Passos mensais, sem horas; as épocas que atravessam o ano usam o dezembro anterior.
- **Valores repetidos e autocorrelação.** Correção de empates e aviso se houver autocorrelação dos resíduos.
- **Mapas.** Média por blocos para no máximo 40 células no lado maior.

## 4. Lista de segurança (replica-backend)

- [x] segredos só em variáveis de ambiente; `.env` no `.gitignore`; nenhum segredo no código ou no cliente
- [x] entrada validada no servidor (esquema Pydantic e validações do serviço)
- [x] ids de resultado com formato fixo (32 hex); nada lê fora de `data/results`
- [x] texto do utilizador escapado nos relatórios HTML
- [x] CORS só para os endereços listados (localhost e o GitHub Pages da equipa)
- [x] limite de tamanho por pedido e limite de análises em paralelo
- [x] erros inesperados não expõem detalhes internos
- [ ] autenticação e limites por utilizador: fora do MVP (a API é pública e sem dados pessoais)
- [ ] `pip audit` das dependências: por correr na vossa máquina
- [ ] política de privacidade: a pergunta de investigação fica guardada em `data/results`; digam-no se publicarem
