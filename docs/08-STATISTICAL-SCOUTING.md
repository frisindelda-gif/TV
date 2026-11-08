# 08 — Statistical Scouting: análise, plano e arquitetura

## 1. O que já existe (reutilizado, não substituído)

| Componente atual | Uso no Statistical Scouting |
|---|---|
| `season_stats` (`SeasonStatLine`): estatísticas por jogador × tipo de competição, com proveniência via snapshot → importação | **São as observações** (MetricObservation). Não se duplicam |
| `player_snapshots`, `players`, `import_runs` | Identidade, época (importação), clube, divisão, idade, valor, salário, contrato, pé, altura |
| Conector do save (fmsave) | Passa a guardar **todos** os campos numéricos das estatísticas (antes só um subconjunto), para a descoberta automática |
| `metrics.py` + `snapshot_metrics` (métricas de desempenho v1) | Mantidos (painel, perfil, lista de jogadores funcionam). Ver conflito C-1 |
| Motor de avaliação por atributos (Position Lab) | Independente: avalia atributos, não estatísticas. Os Composite Scores seguem o mesmo padrão (modelo original só de leitura, cópias editáveis) |

## 2. Conflitos identificados

- **C-1 — Dois sistemas de métricas estatísticas.** O módulo v1 (`metrics.py`, 36 métricas)
  e o novo catálogo global. Decisão: o catálogo global passa a ser a referência; o v1 fica
  como está até ser migrado para o novo motor (próximo passo, sem perda de funcionalidade).
- **C-2 — Grupos de posição diferentes.** Os rankings por atributos usam 8 grupos (extremos
  incluem MD/ME); o documento define 9 (MD/ME separados de AD/AE). O Statistical Scouting usa
  os 9 do documento; o motor de atributos mantém os seus.
- **C-3 — "Competição".** O FM guarda o tipo de competição (liga, taça, continental) mas o
  save lido pelo fmsave não identifica *qual* liga sem um mapa de nomes externo. A leitura da
  memória dá o nome da divisão. Quando a competição é desconhecida, o universo de comparação
  junta todas as competições e isso é **sempre indicado**.
- **C-4 — Fontes sem estatísticas.** A leitura da memória (FMSuperScout) não lê estatísticas:
  nessas importações todas as métricas ficam `UNAVAILABLE` com essa explicação.

## 3. Arquitetura

```
CATÁLOGO GLOBAL (código, versionado; sincronizado para a BD)       independente do save
  source_fields.py   campos de origem canónicos (unidade, descrição)
  catalog_data.py    métricas (fórmulas, direção, tipo, unidade…) + mapa por posição/secção
        │
SAVE (por importação)                                              independente do catálogo
  season_stats ──► MetricMappingService (campos do save → campos canónicos, por fonte)
        │                └─► SaveMetricDiscoveryService (campos não mapeados → propostas)
        ▼
  MetricAvailabilityService  AVAILABLE / CALCULABLE / PARTIAL / UNAVAILABLE / INVALID / CUSTOM
        ▼
  DerivedMetricEngine (numpy, vetorizado)  totais, /90, %, rácios, derivadas
        ▼
  PercentileCalculationService  universo configurável, percentil, ranking, média, mediana…
        ▼
  CompositeScoreService · StatisticalRankingService · AdvancedPlayerFilterService
  PlayerComparisonService · PlayerStatisticalProfileService · Market Opportunities
```

### Persistido vs calculado

| Persistido (BD) | Calculado e mantido em cache |
|---|---|
| definições de métricas (built-in sincronizadas + personalizadas aprovadas), mapa posição/secção | valores derivados por jogador (totais, /90, %) |
| observações (`season_stats`) com proveniência | percentis, rankings, médias/medianas do universo |
| disponibilidade por importação, inventário de campos do save | resultados de Composite Scores |
| propostas de novas métricas | |
| Composite Score definitions, pesquisas guardadas, shortlists | |

Porquê: 60 000–100 000 jogadores × ~120 métricas × vários universos dariam dezenas de
milhões de linhas por importação. O cálculo vetorizado de uma importação inteira demora
milissegundos e fica em cache por importação (as importações são imutáveis); só muda quando
há uma importação nova. Mudar um filtro visual não recalcula percentis já calculados.

## 4. Fases (ordem do pedido)

1. Catálogo global · 2. Motor de métricas derivadas · 3. Percentis e rankings ·
4. Composite Scores · 5. Interface · 6. Descoberta no save · 7. Disponibilidade ·
8. Market Opportunities · 9. Testes e desempenho.

Cada fase tem testes próprios e só se avança com eles a passar.

## 5. O que foi implementado (por fase)

| Fase | Resultado | Testes |
|---|---|---|
| 1. Catálogo global | 125 métricas, 108 campos de origem, 225 vistas (total e /90); mapa por posição com 553 entradas em 9 grupos e todas as secções do documento (o teste confere o número de itens de cada secção); 28 entradas transversais; 6 Composite Scores iniciais | `test_stats_catalog.py` |
| 2. Motor de métricas derivadas | Totais, /90, percentagens, rácios, derivadas e fórmulas alternativas (p.ex. defesas = agarradas + para a frente + desviadas) | `test_stats_engine.py` (cada percentagem, derivada e regra de NULL) |
| 3. Percentis e rankings | Universo configurável, percentil com empates a meio, direção, ranking, média, mediana, melhor, pior, cobertura, amostra mínima | `test_stats_percentiles.py` |
| 4. Composite Scores | Pesos editáveis, inversão, normalização pelos pesos disponíveis, cobertura mínima, modelos iniciais só de leitura, duplicar/criar | `test_stats_api.py` |
| 5. Interface | 11 secções em `/stats` + perfil estatístico no perfil do jogador (9 separadores) | testes de browser |
| 6. Descoberta | Inventário dos campos do save, mapeamento por fonte, propostas com significado, unidade, tipo, posições e equivalente; aprovação/rejeição | `test_stats_api.py` |
| 7. Disponibilidade | Seis estados por importação, com explicação; nunca altera o catálogo | `test_stats_api.py` |
| 8. Market Opportunities | Desempenho (Composite ou percentil) × valor, salário, contrato, transferível/emprestável, PA − CA; "£ por ponto" identificado como derivado | `test_stats_api.py` |
| 9. Volume | Ver abaixo | medições manuais |

## 6. O que um save do fmsave fornece (medido na demonstração, que usa os mesmos campos)

- **36 AVAILABLE**, **18 CALCULABLE**, **2 PARTIAL**, **69 UNAVAILABLE**, **0 INVALID** (de 125).
- Indisponíveis porque o fmsave não expõe o campo: ações defensivas, cortes, duelos
  defensivos/ofensivos/totais, conduções, dribles tentados, passes longos, verticais, para o
  último terço, que quebram linhas, toques, recuperações por meio-campo, pressões por zona,
  golos de cabeça/pé, grandes ocasiões falhadas, etc. Continuam no catálogo.
- 16 campos do save sem correspondência no catálogo foram propostos como novas métricas
  (xG, npxG, xA, nota média, distância, sprints, foras de jogo, desarmes e cabeceamentos
  decisivos, passes-chave e cruzamentos em jogo corrido, remates de livre, golos de fora da
  área, penáltis batidos, melhor em campo).
- Consequência nos Composite Scores iniciais: "Central Defensivo Dominante" fica com 57 % das
  componentes e "Central Construtor" e "Extremo Desequilibrador" com 43 %, abaixo da
  cobertura mínima de 60 %: não mostram score (mostram a cobertura). Pode-se duplicá-los com
  outra cobertura mínima ou outras componentes.

## 7. Desempenho (100 000 jogadores com estatísticas)

| Operação | Tempo |
|---|---|
| Importar + avaliar + estatísticas | 43 s |
| 1.ª consulta depois de arrancar a app (carrega a importação para a cache) | 5 s |
| Pesquisa/ranking seguintes | 20–240 ms |
| Filtro E/OU com percentis | 130 ms |
| Perfil estatístico (1.ª vez / seguintes) | 1,4 s / 70 ms |
| Comparação, overview, mercado, exportação CSV | < 100 ms |

Defeito encontrado e corrigido pelo teste de volume: uma consulta com milhares de ids
excedia o limite de parâmetros do SQLite.

## 8. Limitações conhecidas

- O mapeamento dos campos do fmsave tem correspondências `assumed` (p.ex. "possession won"
  → recuperações) a confirmar contra o ecrã do FM27.
- A competição só é conhecida quando a fonte dá o nome da divisão; no save lido pelo
  fmsave isso não acontece (ver C-3) e o universo junta competições, sempre com aviso.
- O filtro "País" do pedido não foi incluído: nenhuma fonte atual dá o país da competição
  do jogador de forma fiável (o save dá ids de nação sem nomes).
- O módulo de métricas v1 (conflito C-1) continua ativo até ser migrado para o motor novo.
- Pesquisa em linguagem natural: preparada (pedido JSON validado), não implementada.
