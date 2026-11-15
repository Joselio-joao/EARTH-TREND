# Fontes NASA e integração no EarthTrend AI

Este documento distingue os produtos consultados directamente pelo backend das ferramentas externas de exploração e extracção.

## Produtos ligados ao backend

| Produto | Variável | Dados de origem | Tratamento no EarthTrend AI |
|---|---|---|---|
| GPM IMERG Final V07 | Precipitação | Mensal, taxa em mm/hr | Média espacial regional; taxa convertida em acumulação mensal antes da análise |
| MODIS Terra MOD13Q1.061 | NDVI | Compósitos de 16 dias, 250 m | Escala 0,0001; apenas pixels SummaryQA = 0; média mensal regional |
| MODIS Terra MOD13Q1.061 | EVI | Compósitos de 16 dias, 250 m | Escala 0,0001; apenas pixels SummaryQA = 0; média mensal regional |
| GLDAS-2.1 Noah | Humidade do solo 0–10 cm | Instantâneo, 3 horas, ~27,8 km | Média mensal das estimativas disponíveis |
| GLDAS-2.1 Noah | Temperatura do ar | Instantâneo, 3 horas, ~27,8 km | Conversão K para °C; média mensal das estimativas disponíveis |

### MODIS

Fonte: [MOD13Q1.061 — catálogo do Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1).

NDVI e EVI são índices espectrais adimensionais. Não devem ser interpretados como medições directas de biomassa, produtividade ou saúde de um ecossistema. O filtro SummaryQA = 0 privilegia pixels classificados como bons, mas pode deixar meses com menos observações em regiões nubladas.

### GLDAS

Fonte: [GLDAS-2.1 Noah — catálogo do Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H).

GLDAS é um sistema de assimilação/modelação terrestre. Os resultados são estimativas modeladas e a resolução de aproximadamente 27,8 km não permite conclusões sobre diferenças ambientais muito locais.

## Ferramentas NASA externas

Estas ferramentas estão ligadas na Biblioteca de Dados como pontos de entrada, mas não são confundidas com conectores automáticos do backend:

- [NASA Giovanni](https://giovanni.gsfc.nasa.gov/giovanni/) — exploração, visualização e análise de variáveis geofísicas; o acesso completo pode exigir Earthdata Login.
- [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/) — extracção de dados por ponto ou polígono, com selecção temporal, espacial e de bandas; pedidos de extracção exigem autenticação Earthdata.
- [Hydrology Time Series](https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series) — ferramenta do GES DISC para séries hidrológicas por localização e período.

Exportações dessas ferramentas só devem entrar numa análise depois de confirmar variável, unidade, calendário, qualidade, versão e formato. O carregador de ficheiros do backend aceita séries CSV mensais e grelhas NetCDF/HDF5, mas não transforma automaticamente qualquer exportação num produto compatível.

## Fontes em preparação

- [SWOT — PO.DAAC/JPL](https://podaac.jpl.nasa.gov/SWOT): missão relevante para altura e extensão de águas superficiais. A integração exige seleccionar o produto e versão adequados, confirmar cobertura em Angola e implementar o acesso aos granules.
- [NASA GISTEMP](https://data.giss.nasa.gov/gistemp/): análise de anomalias de temperatura; a escala espacial deve ser avaliada antes de a usar para províncias.
- KNMI Climate Explorer é uma ferramenta externa de análise climática, não um produto NASA.
- RADARSAT Constellation Mission e Geo.ca são recursos canadenses; não são prioridade para o estudo de Angola sem uma cobertura útil confirmada.

## Limite cartográfico actual

O conector Earth Engine aqui descrito devolve séries temporais regionais. Não devolve, por enquanto, um raster espacial para desenhar mapas de valores ou mapas de tendência. A interface deve continuar a indicar essa limitação até existir uma camada raster real, com legenda, unidade, período, resolução e proveniência.
