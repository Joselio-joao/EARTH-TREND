# Plano de testes do backend

Formato do pack replica-test. Comando: `cd backend && python -m unittest discover -s tests -v`.
Última execução (ambiente de criação, só numpy e scipy): **100 testes, 91 executados e a passar, 9 saltados**
(3 de leitura de NetCDF, 6 de HTTP: precisam de `xarray`, `fastapi` e `httpx`, e estão escritos para correr
na vossa máquina). Os dados são sintéticos e só existem nos testes.

| caso | fluxo | tipo | o que verifica | auto | resultado |
| --- | --- | --- | --- | --- | --- |
| F01-H1 | análise anual | feliz | série conhecida dá aumento, declive ≈ 3,65 mm/ano por ano, p < 0,001 | sim | passou |
| F01-H2 | unidades | feliz | mm/h e mm/dia dão a mesma série | sim | passou |
| F01-H3 | escala mensal | feliz | Mann-Kendall sazonal, 240 observações | sim | passou |
| F01-H4 | época DJF | feliz | usa o dezembro do ano anterior; total = soma dos 3 meses | sim | passou |
| F01-E1 | anos incompletos | limite | excluídos e avisados, nunca preenchidos | sim | passou |
| F01-E2 | série curta | limite | menos de 10 anos: inconclusivo, sem números inventados | sim | passou |
| F01-E3 | células em falta | limite | NaN fora da média, `cells_used_mean` = 24 | sim | passou |
| F01-E4 | contorno | limite | média só nas 15 células do polígono (buraco e multipolígono testados) | sim | passou |
| F01-E5 | período fora dos dados | limite | erro 422 com a cobertura real | sim | passou |
| F01-N1 | unidade desconhecida | negativo | `mm`, `mm/month`, `degC` recusadas (422) | sim | passou |
| F01-N2 | sem dados no servidor | negativo | 409 `data_unavailable`, nunca números | sim | passou |
| F01-N3 | pedido enorme | negativo | região global recusada antes de ler dados | sim | passou |
| F01-N4 | servidor ocupado | negativo | 429, e a vaga é libertada mesmo com erros | sim | passou |
| F01-N5 | ids maliciosos | negativo | `../../etc/passwd` e afins dão 404 | sim | passou |
| F01-N6 | texto do utilizador | negativo | `<script>` na pergunta sai escapado no relatório | sim | passou |
| STAT-01 | motor | estatística | erro tipo I = 4,9% com α = 5% (1500 séries de ruído) | sim | passou |
| STAT-02 | motor | estatística | potência 100% com tendência clara | sim | passou |
| STAT-03 | motor | estatística | cobertura do IC de 95% do declive = 96,5% | sim | passou |
| STAT-04 | motor | estatística | falsos positivos sazonais = 4,3% | sim | passou |
| STAT-05 | motor | verificação cruzada | S e Var(S) iguais à definição de livro (com empates); declive igual ao `scipy.stats.theilslopes` | sim | passou |
| IO-01 | CSV | feliz e negativo | cabeçalhos do Giovanni, unidades obrigatórias, duplicados, linhas inválidas | sim | passou |
| IO-02 | NetCDF | feliz e negativo | recorte, ordenação, nomes de coordenadas, preenchimentos, erros | sim | escrito, não executado aqui |
| API-01 | HTTP | fluxo completo | `TestClient`, CORS, erros JSON | sim | escrito, não executado aqui |
| API-02 | HTTP | fumo | os handlers das rotas chamam o serviço (com módulos `fastapi` falsos) | ad hoc | passou |
| REAL-01 | dados | manual | ficheiros IMERG reais abrem e `describe` mostra o que o registo espera | não | por fazer |
| REAL-02 | validação | manual | série de Angola igual à do Giovanni | não | por fazer |

## Por fazer antes da demonstração

- REAL-01 e REAL-02, com dados descarregados da conta Earthdata da equipa.
- Correr `pip install -r requirements-dev.txt` e a suite completa (os 9 testes saltados passam a correr).
- Comparar com uma implementação independente: `pymannkendall.original_test` na série anual.
