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
pytest -q backend/tests
```

O próximo passo será criar o endpoint de regiões, antes de ligar os dados científicos reais.
