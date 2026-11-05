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

O front-end é estático e responsivo, com estado persistente em `localStorage`. Os resultados apresentados no Trend Lab são **amostras demonstrativas** para validar a experiência; não representam medições reais nem resultados oficiais da NASA.

A interface já está preparada para a futura arquitetura prevista no documento: React/Frontend → FastAPI → dados processados NASA → motor estatístico Python. A próxima integração deverá substituir os valores de `assets/app.js` por respostas do backend, mantendo a proveniência, unidades, método, incerteza e limitações no relatório.

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
