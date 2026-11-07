# 05 — Métricas

Todas as métricas são **derivadas** de valores lidos do jogo (estado `derived`): nunca são
estimadas. Um valor sem dados ou sem denominador (p.ex. 0 remates) fica vazio.

## Fonte
- Estatísticas da época atual vêm do **Save Reader** (`player_season_stats` do fmsave).
  A leitura da memória (FMSuperScout) não tem estatísticas, logo não gera métricas.
- Linhas usadas: a linha "overall" quando existe; senão a soma das competições de clube
  (liga, taças, continentais). Seleção nacional e particulares ficam de fora.
- A carreira de demonstração tem estatísticas **fictícias**, geradas a partir dos atributos,
  só para mostrar a interface.

## Desempenho (`backend/fm27si/metrics.py`)
- Por 90 minutos: golos, xG, xG sem penáltis, remates, assistências, xA, passes decisivos,
  ocasiões claras, passes progressivos, dribles, desarmes ganhos, interceções, posse ganha,
  pressões, cabeceamentos ganhos, alívios, bloqueios, distância, sprints, posse perdida,
  faltas; guarda-redes: xGP e golos sofridos.
- Percentagens: remates à baliza, conversão, passes, cruzamentos, desarmes, duelos aéreos;
  guarda-redes: defesas e jogos sem sofrer.
- Totais: golos − xG, erros que deram golo, nota média (ponderada por jogos), minutos, jogos.
- Métricas de guarda-redes só para guarda-redes; as de campo só para jogadores de campo.

## Percentis por posição
- Grupos: guarda-redes, defesas centrais, laterais, médios defensivos, médios centro,
  extremos/alas, médios ofensivos, pontas-de-lança (pela primeira posição natural).
- Comparação dentro da **mesma importação**, só com quem jogou **≥ 450 minutos**, e só se o
  grupo tiver pelo menos 5 jogadores. Percentil = % de pares abaixo + metade dos empatados.
- Em métricas onde menos é melhor (faltas, posse perdida, golos sofridos, erros) o
  percentil é invertido: 100 continua a ser o melhor.
- Radar no perfil com 7–8 métricas típicas de cada grupo, contra a mediana (50).

## Crescimento
- Cada snapshot guarda a variação de CA e PA em relação ao snapshot anterior do mesmo
  jogador: o de data de jogo mais recente que não seja posterior (importar um save antigo
  depois não estraga a comparação).
- "Novo nesta importação" = jogador que ainda não existia na carreira. Na primeira
  importação de uma carreira fica indefinido.

## Onde aparecem
- **Painel** (`/painel`): números gerais, distribuições de CA e PA, maiores subidas, melhores
  regens novos, maiores potenciais, melhor nota, mais golos/90, resumo por posição e clubes.
- **Jogadores**: ordenar por qualquer métrica ou crescimento; filtrar por valor ou percentil
  de métrica, grupo de posição, minutos mínimos, CA ganho, só novos; filtros rápidos.
- **Perfil**: radar de percentis, lista completa por grupo com barra de percentil, variação de CA.

## API
- `GET /api/metrics` — catálogo (métricas, grupos de posição, radar, mínimo de minutos).
- `GET /api/players?sort=m:goals_90&min_minutes=900` · `min_metric=pass_pct:85` ·
  `min_percentile=xg_90:80` · `position_group=ST` · `sort=ca_delta` · `new_only=true`.
- `GET /api/players/{id}` → `metrics` (valores, percentis, pares) e `growth`.
- `GET /api/overview` — painel.
