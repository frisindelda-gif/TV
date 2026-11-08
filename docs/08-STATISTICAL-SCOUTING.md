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
