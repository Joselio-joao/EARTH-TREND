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

O endpoint confirma a província, a variável ambiental e o período. Devolve uma configuração com estado `configured`. Ainda não descarrega dados nem executa a análise.

## Passo 5: motor de tendências

Endpoint:

```text
POST /analyze
```

O motor calcula regressão linear, R², inclinação de Sen e Mann–Kendall. Os dados `synthetic_test` servem apenas para validar o algoritmo; não são apresentados como dados NASA.

## Passo 6: carregador de dados científicos

O módulo `app/data/load_data.py` lê dois formatos comuns em dados ambientais:

- CSV, com colunas de data e valor configuráveis;
- NetCDF, identificando uma variável temporal e calculando a média das dimensões espaciais.

O carregador normaliza as observações para o mesmo formato usado pelo motor estatístico. Datas e valores inválidos são removidos e contabilizados. Observações repetidas no mesmo dia são agregadas pela média. O carregador não assume que todos os produtos NASA têm as mesmas unidades, nomes de variáveis ou resolução; esses metadados devem ser confirmados por produto antes da análise.

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

O próximo passo será ligar um ficheiro científico real ao carregador e confirmar unidades, qualidade e cobertura temporal.

## Passo 7: manifesto GPM IMERG

Endpoint de fontes científicas:

```text
GET /data-sources
```

O manifesto regista o GPM IMERG Final Daily V07, os formatos documentados, as opções temporais, a resolução espacial e o estado de acesso. A fonte está marcada como `metadata_registered_file_not_downloaded`: não é apresentada como se já existisse um ficheiro NASA local. As unidades e os atributos do ficheiro serão confirmados quando o ficheiro real for disponibilizado através do Earthdata.

## Passo 8: validar um ficheiro científico

Endpoint:

```text
POST /data/validate?variable_name=precipitationCal
```

O endpoint recebe um ficheiro `.nc`, `.nc4` ou `.netcdf` e valida a variável, a dimensão temporal, as unidades, a resolução das coordenadas, o número de linhas e os valores ausentes. O ficheiro é usado temporariamente durante a validação e não é guardado permanentemente.

## Passo 9: análise de um ficheiro validado

Endpoint:

```text
POST /data/analyze?investigation_id=...&variable_name=precipitationCal
```

Esta rota executa a validação, carrega a série temporal, agrega as dimensões espaciais por média e envia as observações para o motor de tendências. O resultado fica marcado como `scientific_dataset`. O ficheiro continua temporário e não é guardado permanentemente.

## Passo 10: consultar resultados

Os resultados recebem um identificador próprio e podem ser consultados enquanto o processo do backend estiver ativo:

```text
GET /results
GET /results/{result_id}
```

Este armazenamento é temporário e fica em memória. Reiniciar o backend elimina os resultados; uma base de dados será considerada numa etapa posterior, quando a estrutura científica estiver estabilizada.

## Passo 11: relatório HTML

Endpoint:

```text
GET /report/{result_id}
```

O relatório reúne a origem dos dados, configuração, metodologia, métricas, limitações e avisos de validação. A resposta é HTML imprimível e pode ser guardada pelo navegador como PDF. Não apresenta causalidade nem inventa informação que não esteja no resultado.
