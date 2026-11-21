# Angola — contorno nacional offline

Este ficheiro é uma camada de referência visual para manter o mapa nacional visível sem depender da API.

## Proveniência
- Fonte geométrica de origem: geoBoundaries, camada AGO ADM1 simplificada, ano representativo 2021.
- O contorno nacional foi obtido pela dissolução das fronteiras internas das 18 geometrias provinciais de origem e simplificado para visualização em escala nacional.
- A geometria usada aqui representa apenas o contorno externo de Angola continental e Cabinda. Não é uma camada de limites provinciais.

## Limitação administrativa
A Lei n.º 14/24, de 5 de Setembro de 2024, estabelece 21 províncias, 326 municípios e 378 comunas. O ficheiro de origem ADM1 de 2021 contém 18 unidades e, por isso, não deve ser usado para identificar ou analisar as atuais fronteiras provinciais. A camada offline deste frontend serve apenas como mapa-base nacional e enquadramento visual.

A aplicação deve usar uma camada administrativa atualizada e licenciada antes de disponibilizar análise por cada uma das 21 províncias. Não utilizar esta geometria como limite cadastral, legal ou de decisão administrativa.

## Atribuição
- geoBoundaries: https://www.geoboundaries.org
- Runfola et al. (2020), “geoBoundaries: A global database of political administrative boundaries”: https://doi.org/10.1371/journal.pone.0231866
- Fonte indicada nos metadados do conjunto original: U.S. Census Bureau
- Distribuição geoBoundaries: atribuição CC BY 4.0, conforme a documentação do repositório de origem.

Gerado a partir de `backend/data/regions/angola.geojson` já presente no repositório. Não são introduzidas novas fronteiras provinciais.

## Utilização no EarthTrend Search

A mesma geometria dissolvida é copiada para `backend/data/regions/angola-national-outline.geojson` e usada como filtro espacial `intersects` nas consultas STAC de produtos Copernicus. O objectivo é limitar a descoberta de produtos à área nacional de referência. A camada não é usada como fronteira provincial, limite cadastral ou base para decisões legais.
