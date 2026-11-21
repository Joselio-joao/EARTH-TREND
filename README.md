# EarthTrend AI

Frontend funcional para o projeto NASA Space Apps Challenge — Luanda **Be an Earth System Trend Detective!**

A aplicação conduz o utilizador por um fluxo de investigação ambiental:

1. escolher região e variável;
2. configurar período e agregação temporal;
3. visualizar mapa e série temporal;
4. consultar direção, magnitude, valor-p e número de observações;
5. guardar investigações localmente;
6. exportar um relatório de texto reproduzível.

## Estado atual

O repositório contém uma interface React/Vite responsiva e um backend FastAPI publicado separadamente.

- **Interface pública:** https://joselio-joao.github.io/EARTH-TREND/
- **API:** https://earthtrend-ai-api.onrender.com
- **Análise configurada:** Google Earth Engine continua a ser o fornecedor activo para os produtos ligados ao pipeline actual.
- **Estatísticas de tendência:** o resumo inclui medidas descritivas complementares, variação absoluta e percentual, dispersão e amplitude, sem confundir descrição com significância estatística.
- **Mapa de Angola:** o contorno nacional é servido como GeoJSON local no frontend, pelo que permanece visível sem backend. Esta camada nacional não contém divisões provinciais.
- **EarthTrend Search:** pesquisa o catálogo local, encontra coleções Copernicus ao vivo e consulta registos Sentinel que intersectam o contorno nacional de Angola, filtrados por período. Os resultados externos são metadados; os ficheiros e bandas ainda não são descarregados nem analisados.
- **Catálogo multi-fonte:** inclui NASA, Copernicus, NOAA, USGS, ESA e outras plataformas como fontes de pesquisa, com o estado de integração identificado.

As séries e mapas de análise devem ser interpretados com a fonte, versão, cobertura temporal, unidade, qualidade e limitações apresentadas no resultado. Os dados externos ainda não integrados não são apresentados como disponíveis para análise.

## Páginas

- `index.html` — visão geral e entrada no fluxo;
- `explore.html` — região, variável e pergunta;
- `trend-lab.html` — configuração, gráfico e resumo da tendência;
- `investigate.html` — quadro local e impressão;
- `data-library.html` — GPM IMERG, MODIS, GISTEMP e GLDAS;
- `methodology.html` — pipeline e regras científicas;
- `about.html` — proposta de valor e referências.

Para testar localmente:

```bash
python3 -m http.server 4173
```
## Site online

Link público do site: **https://joselio-joao.github.io/EARTH-TREND/**

Para ativar a publicação no GitHub: abre **Settings → Pages**, escolhe **Deploy from a branch**, seleciona a branch `main` e a pasta `/ (root)`, e clica em **Save**.

## Mapa-base de Angola

A interface inclui `frontend/public/data/angola-national-outline.geojson`, um contorno nacional simplificado que é carregado localmente no frontend e não depende da API.

A geometria foi derivada da camada geoBoundaries AGO ADM1 (ano representativo 2021) já presente em `backend/data/regions/angola.geojson`. As fronteiras provinciais internas foram dissolvidas: esta camada mostra apenas o contorno nacional de Angola continental e Cabinda.

**Limitação importante:** a camada de origem contém 18 unidades administrativas e não representa a divisão político-administrativa atual de 21 províncias estabelecida pela Lei n.º 14/24, de 5 de Setembro de 2024. Por isso, o mapa offline não apresenta limites provinciais atuais. A aplicação só deverá disponibilizar análise provincial para a nova divisão depois de integrar uma fonte geográfica atualizada, com proveniência e licença verificadas.

A atribuição, a proveniência e as limitações desta camada estão documentadas em `frontend/public/data/ANGOLA-NATIONAL-OUTLINE-SOURCE.md`. O mesmo contorno nacional é utilizado como geometria `intersects` na pesquisa de produtos Copernicus, sem afirmar precisão cadastral ou limites provinciais actuais.
