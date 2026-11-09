# EarthTrend AI — Backend

## Passo 1: API mínima

Este passo cria a aplicação FastAPI e o endpoint de verificação:

```text
GET /health
```

## Executar localmente

A partir da raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

A API fica disponível em `http://127.0.0.1:8000`.

## Validar

```bash
curl http://127.0.0.1:8000/health
pytest -q backend/tests
```

A análise NASA, os datasets e os endpoints científicos serão adicionados nos passos seguintes, depois de validar esta fundação.
