# 06 — Motor de avaliação por posição e função

> **Estado da especificação:** a especificação "Position Metrics" referida no pedido não
> foi recebida. O motor está completo e é configurável; os pesos atuais são uma **proposta
> inicial** (`backend/fm27si/evaluation/defaults.py`, documentada em
> [`07-PESOS.md`](07-PESOS.md)). Substituí-los pela especificação real não exige alterar o
> motor nem a interface.

## Arquitetura (motor separado da interface)

```
atributos (1–20, por snapshot)          ← dados extraídos do jogo
      │  normalização n(a) = (a − 1) / 19 × 100
      ▼
métricas (0–100)    técnicas · mentais · físicas · táticas · específicas da posição
      │  média ponderada das métricas
      ├──► Position Score (12 posições)
      └──► Role Score (funções ativas)
```

| Módulo | Função |
|---|---|
| `evaluation/spec.py` | Esquema validado (Pydantic) da especificação: métricas, posições, funções, hash |
| `evaluation/engine.py` | Cálculo puro e vetorizado (numpy). Sem BD, sem HTTP |
| `evaluation/defaults.py` | Modelo original (proposta inicial) |
| `evaluation/service.py` | Avaliação em lote por importação, médias por posição, rankings, perfil |
| `evaluation/docs.py` | Gera `07-PESOS.md` a partir do modelo |
| `api_evaluation.py` | Endpoints do Position Lab, rankings e avaliação no perfil |

## Fórmulas

1. **Normalização:** `n(a) = (a − 1) / 19 × 100` (1 → 0, 20 → 100). Valores > 20 (saves
   editados) limitados a 100. Atributos invertidos (p.ex. propensão a lesões): `100 − n(a)`.
2. **Métrica:** `Σ wᵢ·n(aᵢ) / Σ wᵢ`, somando **só os atributos disponíveis**.
   **Cobertura** = peso disponível / peso total.
3. **Posição / função:** a mesma média ponderada sobre as **métricas calculadas**.
   Cobertura = `Σ (peso × cobertura da métrica) / Σ pesos`.
4. **Dados em falta:** nunca contam como zero. Se a cobertura ficar abaixo do mínimo do
   modelo (60 % por omissão) o resultado fica **por calcular**.
5. **Confiança:** alta (cobertura ≥ 95 % e atributos verificados no jogo), média (≥ 80 %
   ou atributos por confirmar no FM27), baixa (< 80 % ou dados estimados/fictícios).
6. **Reprodutibilidade:** cada modelo tem um `spec_hash` (SHA-256 da especificação
   canónica). Cada avaliação guardada regista o hash; o mesmo hash com os mesmos atributos
   dá sempre o mesmo resultado (testado). Se os pesos mudarem, os rankings ficam marcados
   como desatualizados até serem recalculados.

## Posições

GR, DD, DC, DE, MDC, MC, MD, MO, ME, AD, PL, AE — códigos internos GK, DR, DC, DL, DM, MC,
MR, AMC, ML, AMR, ST, AML (os do FM). Laterais/alas WBL/WBR e líbero não foram pedidos.

**Competência:** um jogador é "competente" numa posição se ela estiver nas suas posições
naturais/competentes ou tiver classificação FM ≥ 15. Os rankings usam só competentes (pode
desligar-se); a melhor função só considera funções dessas posições.

## Funções

Só as 13 funções indicadas, todas marcadas **por confirmar no FM27** (não há forma de ler
a lista de funções do jogo instalado: nenhuma das duas fontes a expõe). No Position Lab
pode desativar as que não existirem, marcar as confirmadas e criar novas.

## Rankings

Guarda-redes (GR), centrais (DC), laterais (DD/DE), médios defensivos (MDC), médios centro
(MC), médios ofensivos (MO), extremos e alas (AD/AE/MD/ME), avançados (PL). A pontuação de
um grupo é a melhor das suas posições em que o jogador é competente. Ordenação por Position
Score, por posição do grupo, por qualquer função, CA, PA, idade, valor ou CA ganho; filtros
por idade, confiança e competência.

## Perfil

Position Scores no campo (clique para analisar outra posição), Role Scores, posição em
análise com média e ranking entre competentes (top 5 e vizinhos), pontos fortes e fracos
(métricas acima/abaixo da média da posição, ponderadas pela importância), comparação
métrica a métrica com a média, radar dos 8 atributos mais importantes contra a média,
e todas as métricas por categoria com os atributos usados, os em falta e a cobertura.

## Position Lab

Consultar métricas, atributos e fórmulas; editar pesos; criar métricas e funções; editar o
modelo de cada posição (com "copiar pesos de"); duplicar, guardar, ativar, apagar e
restaurar modelos; pré-visualizar o efeito num jogador antes de guardar; recalcular os
rankings. O modelo original é só de leitura.

## Atributos vs indicadores vs estatísticas

- **Atributos**: valores do jogo (tabela `snapshot_attributes`), nunca alterados.
- **Indicadores de avaliação**: calculados a partir dos atributos por este motor.
- **Métricas de desempenho**: derivadas das estatísticas de jogo (`05-METRICAS.md`).
A interface identifica sempre qual é qual.

## Desempenho medido

60 000 jogadores avaliados em ~0,6 s (motor) e ~6 s com escrita na BD.

## Evolução para scouting real

Nada no motor é específico do FM além do catálogo de atributos: trocar o catálogo e a
normalização (p.ex. notas de 0–100 de um relatório de observação) reutiliza métricas,
posições, funções, cobertura e confiança.
