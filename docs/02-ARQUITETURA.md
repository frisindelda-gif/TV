# 02 — Arquitetura recomendada

```
                ┌──────────────── Windows (máquina do utilizador) ────────────────┐
                │                                                                  │
 FM27 (fm.exe)  │  FMSuperScout.Scanner.exe scan      ficheiro .fm (save)          │
   memória ─────┼──► (só PROCESS_VM_READ)                  │                       │
                │        │ dump.json                       │ cópia temporária      │
                │        ▼                                 ▼                       │
                │  ┌─────────────────────┐      ┌─────────────────────┐            │
                │  │ Live Connector      │      │ Save Reader         │            │
                │  │ live_fmsuperscout.py│      │ save_fmsave.py      │            │
                │  └─────────┬───────────┘      └──────────┬──────────┘            │
                │            └──────► ImportBundle ◄───────┘   (schemas.py)        │
                │                          │                                       │
                │                 validation.py (CA/PA/atributos)                  │
                │                          │                                       │
                │                 importer.py ──► SQLite (orm.py)                  │
                │                          │      careers · import_runs · clubs    │
                │                          │      players · player_snapshots       │
                │                          │      snapshot_attributes · issues     │
                │                          │      season_stats                     │
                │                 api.py (FastAPI, 127.0.0.1:8727)                 │
                │                          │                                       │
                │                 frontend React/TS/Tailwind/shadcn/Recharts       │
                │                 (Vite, 127.0.0.1:5173, proxy /api)               │
                └──────────────────────────────────────────────────────────────────┘
```

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `catalog.py` | Lista canónica dos 60 atributos (52 + 8 personalidade), categorias e nomes em cada fonte |
| `schemas.py` | Contrato normalizado (Pydantic) — a única coisa que os conectores produzem |
| `connectors/` | Um ficheiro por fonte; nenhum escreve em lado nenhum |
| `validation.py` | Regras de CA/PA/atributos/posições; nunca altera valores |
| `importer.py` | Persistência em lote, identidade, idempotência, histórico |
| `integrity.py` | Verificações SQL pós-importação |
| `api.py` | Endpoints HTTP |
| `testdata.py` | Gerador da carreira de teste sintética |

## Modelo de dados

- `careers` — uma carreira (chave explícita ou heurística).
- `import_runs` — **origem e data** de cada importação: conector, ferramenta e versão,
  caminho, sha256, data de modificação, data da leitura, data de entrada na BD, data no
  jogo (+ estado), época derivada, versão do jogo, moeda, flag sintética, campos
  indisponíveis, avisos.
- `players` — identidade estável (`uid:<Unique ID>`), primeira/última importação em que foi visto.
- `player_snapshots` — valores no momento: CA, PA, código de PA, clube, contrato, valor,
  posições, reputações, `field_status` por campo, `quality`.
- `snapshot_attributes` — 60 colunas, NULL = não fornecido.
- `season_stats` — estatísticas por época/tipo de competição.
- `validation_issues` — problemas por snapshot.

## Endpoints da PoC

| Método | Caminho | Função |
|---|---|---|
| GET | `/api/health` | Estado |
| GET | `/api/attributes` | Catálogo de atributos |
| POST | `/api/import/live` | `{dump_path?, run_scanner?, scanner_path?, career_key?}` |
| POST | `/api/import/save` | `{path, career_key?}` |
| GET | `/api/careers` · `/api/careers/{id}/runs` | Carreiras e importações |
| GET | `/api/players` | Lista com filtros: `q, club, position, min_ca, min_pa, max_age, min_attr=pace:15` (repetível), `sort, order, limit, offset, run_id, career_id` |
| GET | `/api/players/{id}` | Perfil completo: identidade, CA/PA, atributos por categoria, posições, contrato, estatísticas, problemas, `field_status`, proveniência, campos indisponíveis, histórico |
| GET | `/api/runs/{id}/integrity` | Relatório de integridade |

## Recomendação de evolução (próximas etapas, por ordem)

1. **Teste de aceitação em Windows** com FM27 real: um save `.fm` e uma leitura live da
   mesma data de jogo (ver `03-RESULTADOS-POC.md`, secção 7).
2. **Verificação cruzada** memória × save por Unique ID (CA, PA, atributos): onde coincidem,
   promover `unconfirmed` → `verified`; onde divergem, sinalizar. É a forma mais barata de
   ganhar confiança nos dados do fmsave no FM27.
3. **Enriquecimento entre fontes:** nomes de nações/divisões do Live preenchem os ids do Save;
   estatísticas e classificações por posição do Save completam o Live.
4. **Política de retenção de snapshots** antes de permitir atualizações frequentes.
5. Só depois: interface completa, funções (roles) calculadas — sempre marcadas `derived`.
