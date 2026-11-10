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
