# Dados científicos

## GPM IMERG Final Daily V07

O backend já tem o manifesto do produto registado em `app/data/sources.py` e expõe os metadados em:

```text
GET /data-sources
```

A fonte está marcada como `metadata_registered_file_not_downloaded`. Isto significa que a aplicação conhece o produto e as suas características documentadas, mas ainda não guarda um ficheiro NASA local.

Antes de analisar um ficheiro real, devem ser confirmados nos metadados do próprio ficheiro:

- nome exato da variável;
- unidades;
- calendário e dimensão temporal;
- resolução espacial;
- valores de preenchimento;
- indicadores de qualidade.

Fontes oficiais:

- https://gpm.nasa.gov/data/imerg
- https://gpm.nasa.gov/node/3176
- https://www.earthdata.nasa.gov/dashboard/data-catalog/GPM_3IMERGDF.v07

## Limites administrativos de Angola

Os contornos oficiais usados pelo backend estão em `backend/data/regions/`.
O ficheiro `angola.geojson` reúne as 18 unidades administrativas de nível ADM1
e cada província tem também um ficheiro próprio, por exemplo `luanda.geojson`
ou `huila.geojson`. O catálogo em `backend/app/data/regions.json` associa os ids
das regiões a estes ficheiros.

Os dados são a versão simplificada `geoBoundaries-AGO-ADM1` (ano representativo
2021), fornecida pelo geoBoundaries. A fonte da definição dos limites indicada
nos metadados é o U.S. Census Bureau, e a licença declarada é Public Domain.
Para a distribuição do produto geoBoundaries, o projeto pede atribuição CC BY 4.0:

- geoBoundaries: https://www.geoboundaries.org
- Runfola et al. (2020), *geoBoundaries: A global database of political administrative boundaries*: https://doi.org/10.1371/journal.pone.0231866
- Fonte dos limites: https://www.census.gov/geographies/mapping-files/time-series/demo/international-programs/subnationalpopulation.html

Os ficheiros são usados apenas como contornos geográficos para a máscara espacial;
não alteram os valores dos datasets ambientais nem substituem a confirmação da
proveniência dos dados científicos.
