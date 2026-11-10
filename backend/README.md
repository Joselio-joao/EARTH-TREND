# EarthTrend AI — Backend

## Passo 1: API mínima

Endpoint de verificação:

```text
GET /health
```

## Passo 2: catálogo de variáveis

Endpoint do catálogo ambiental:

```text
GET /datasets
```

O endpoint apresenta as variáveis previstas para a EarthTrend AI, a finalidade de cada investigação, a fonte NASA ou científica associada e o estado atual de integração. Neste momento, o catálogo é informação estruturada; ainda não descarrega dados nem executa análises.

Variáveis incluídas:

- Precipitação — GPM IMERG;
- Vegetação — MODIS NDVI / EVI;
- Temperatura — NASA GISTEMP;
- Humidade do solo — NASA GLDAS;
- Armazenamento de água terrestre — GRACE / GRACE-FO;
- Cobertura florestal — MODIS.

## Passo 3: regiões de Angola

Endpoint das regiões:

```text
GET /regions
```

A resposta inclui Angola, a capital nacional, o código do país, as 21 províncias e as respetivas capitais administrativas. A lista segue o [Portal Oficial do Governo de Angola](https://governo.gov.ao/angola/provincias).

## Passo 4: configurar uma investigação

Endpoint:

```text
POST /investigations
```

Exemplo de pedido:

```json
{
  "country_id": "angola",
  "province_id": "luanda",
  "dataset_id": "gpm-imerg",
  "start_date": "2001-01-01",
  "end_date": "2020-12-31"
}
```

O endpoint confirma a província, a variável ambiental e o período. Devolve uma configuração com estado `configured`. Ainda não descarrega dados nem executa a análise; essa será a etapa seguinte.

## Executar localmente

A partir da raiz do repositório:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

A API fica disponível em `http://127.0.0.1:8000`.

## Validar

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/datasets
curl http://127.0.0.1:8000/regions
pytest -q backend/tests
```

O próximo passo será preparar o carregamento de dados e a análise científica.
