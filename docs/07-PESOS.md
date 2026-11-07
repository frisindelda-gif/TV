# 07 — Pesos: Modelo original (proposta inicial)

> Gerado automaticamente por `fm27si weights-doc` a partir do modelo original.
> Não editar à mão. **Proposta inicial**: a especificação "Position Metrics" do
> utilizador ainda não foi recebida; estes pesos serão substituídos por ela.

Hash do modelo: `411d2a996cf47849` · cobertura mínima: 60%

Normalização: `n(a) = (a − 1) / 19 × 100`. Métrica = média ponderada dos atributos
disponíveis; posição/função = média ponderada das métricas calculadas. Percentagens
abaixo = quota de cada peso no total.

## Métricas

### Técnicas

- **Passe** (`passing`; posições: todas) — Precisão e qualidade do passe em circulação.  
  Atributos: Passe 50%, Primeiro toque 20%, Técnica 20%, Compostura 10%  
  Fórmula: `(5×n(passing) + 2×n(first_touch) + 2×n(technique) + 1×n(composure)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Controlo de bola** (`ball_control`; posições: todas) — Receção e proteção da bola sob pressão.  
  Atributos: Primeiro toque 50%, Técnica 30%, Equilíbrio 10%, Compostura 10%  
  Fórmula: `(5×n(first_touch) + 3×n(technique) + 1×n(balance) + 1×n(composure)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Drible** (`dribbling`; posições: todas) — Capacidade de ultrapassar adversários com bola.  
  Atributos: Drible 45%, Agilidade 18%, Técnica 18%, Equilíbrio 9%, Talento 9%  
  Fórmula: `(5×n(dribbling) + 2×n(agility) + 2×n(technique) + 1×n(balance) + 1×n(flair)) / 11, com n(a) = (a − 1) / 19 × 100`
- **Finalização** (`finishing`; posições: todas) — Eficácia na conclusão dentro da área.  
  Atributos: Finalização 55%, Compostura 27%, Técnica 9%, Primeiro toque 9%  
  Fórmula: `(6×n(finishing) + 3×n(composure) + 1×n(technique) + 1×n(first_touch)) / 11, com n(a) = (a − 1) / 19 × 100`
- **Remate de longe** (`long_shots`; posições: todas) — Ameaça de golo de fora da área.  
  Atributos: Remates de longe 67%, Técnica 22%, Compostura 11%  
  Fórmula: `(6×n(long_shots) + 2×n(technique) + 1×n(composure)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Cruzamento** (`crossing`; posições: todas) — Qualidade dos cruzamentos.  
  Atributos: Cruzamentos 67%, Técnica 22%, Visão 11%  
  Fórmula: `(6×n(crossing) + 2×n(technique) + 1×n(vision)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Jogo de cabeça** (`heading`; posições: todas) — Ganhar e direcionar bolas pelo ar.  
  Atributos: Cabeceamento 60%, Impulsão 30%, Coragem 10%  
  Fórmula: `(6×n(heading) + 3×n(jumping_reach) + 1×n(bravery)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Desarme** (`tackling`; posições: todas) — Recuperar a bola em duelo sem falta.  
  Atributos: Desarme 67%, Decisões 11%, Agressividade 11%, Coragem 11%  
  Fórmula: `(6×n(tackling) + 1×n(decisions) + 1×n(aggression) + 1×n(bravery)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Bolas paradas** (`set_pieces`; posições: todas) — Livres, cantos e penáltis.  
  Atributos: Livres 40%, Cantos 30%, Penáltis 20%, Técnica 10%  
  Fórmula: `(4×n(free_kick_taking) + 3×n(corners) + 2×n(penalty_taking) + 1×n(technique)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Passe criativo** (`creative_passing`; posições: todas) — Passes que desequilibram (visão + execução).  
  Atributos: Visão 40%, Passe 30%, Técnica 20%, Talento 10%  
  Fórmula: `(4×n(vision) + 3×n(passing) + 2×n(technique) + 1×n(flair)) / 10, com n(a) = (a − 1) / 19 × 100`

### Mentais

- **Tomada de decisão** (`decision_making`; posições: todas) — Escolher bem e a tempo.  
  Atributos: Decisões 56%, Antecipação 22%, Compostura 22%  
  Fórmula: `(5×n(decisions) + 2×n(anticipation) + 2×n(composure)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Frieza** (`composure`; posições: todas) — Rendimento sob pressão e em jogos grandes.  
  Atributos: Compostura 71%, Jogos importantes 14%, Decisões 14%  
  Fórmula: `(5×n(composure) + 1×n(important_matches) + 1×n(decisions)) / 7, com n(a) = (a − 1) / 19 × 100`
- **Concentração e regularidade** (`concentration`; posições: todas) — Evitar quebras de atenção e de rendimento.  
  Atributos: Concentração 62%, Consistência 25%, Decisões 12%  
  Fórmula: `(5×n(concentration) + 2×n(consistency) + 1×n(decisions)) / 8, com n(a) = (a − 1) / 19 × 100`
- **Ética de trabalho** (`work_ethic`; posições: todas) — Esforço e vontade ao longo do jogo.  
  Atributos: Índice de trabalho 50%, Determinação 38%, Resistência 12%  
  Fórmula: `(4×n(work_rate) + 3×n(determination) + 1×n(stamina)) / 8, com n(a) = (a − 1) / 19 × 100`
- **Liderança** (`leadership`; posições: todas) — Influência sobre os colegas.  
  Atributos: Liderança 62%, Determinação 25%, Compostura 12%  
  Fórmula: `(5×n(leadership) + 2×n(determination) + 1×n(composure)) / 8, com n(a) = (a − 1) / 19 × 100`
- **Criatividade** (`creativity`; posições: todas) — Imprevisibilidade e imaginação.  
  Atributos: Talento 44%, Visão 33%, Técnica 11%, Decisões 11%  
  Fórmula: `(4×n(flair) + 3×n(vision) + 1×n(technique) + 1×n(decisions)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Coragem e agressividade** (`bravery`; posições: todas) — Disponibilidade para o choque.  
  Atributos: Coragem 50%, Agressividade 38%, Determinação 12%  
  Fórmula: `(4×n(bravery) + 3×n(aggression) + 1×n(determination)) / 8, com n(a) = (a − 1) / 19 × 100`

### Físicas

- **Velocidade** (`speed`; posições: todas) — Velocidade máxima e arranque.  
  Atributos: Velocidade 50%, Aceleração 50%  
  Fórmula: `(5×n(pace) + 5×n(acceleration)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Agilidade e equilíbrio** (`agility`; posições: todas) — Mudanças de direção e estabilidade.  
  Atributos: Agilidade 56%, Equilíbrio 33%, Aceleração 11%  
  Fórmula: `(5×n(agility) + 3×n(balance) + 1×n(acceleration)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Força** (`strength`; posições: todas) — Força nos duelos corpo a corpo.  
  Atributos: Força 75%, Equilíbrio 25%  
  Fórmula: `(6×n(strength) + 2×n(balance)) / 8, com n(a) = (a − 1) / 19 × 100`
- **Resistência** (`stamina`; posições: todas) — Manter a intensidade durante 90 minutos.  
  Atributos: Resistência 62%, Forma física natural 38%  
  Fórmula: `(5×n(stamina) + 3×n(natural_fitness)) / 8, com n(a) = (a − 1) / 19 × 100`
- **Durabilidade** (`durability`; posições: todas) — Condição física e resistência a lesões.  
  Atributos: Forma física natural 44%, Propensão a lesões (invertido) 44%, Resistência 11%  
  Fórmula: `(4×n(natural_fitness) + 4×(100 − n(injury_proneness)) + 1×n(stamina)) / 9, com n(a) = (a − 1) / 19 × 100`

### Táticas

- **Posicionamento defensivo** (`positioning`; posições: todas) — Ocupar o espaço certo sem bola.  
  Atributos: Posicionamento 45%, Antecipação 27%, Concentração 18%, Decisões 9%  
  Fórmula: `(5×n(positioning) + 3×n(anticipation) + 2×n(concentration) + 1×n(decisions)) / 11, com n(a) = (a − 1) / 19 × 100`
- **Marcação** (`marking`; posições: todas) — Acompanhar e anular o adversário direto.  
  Atributos: Marcação 56%, Posicionamento 22%, Concentração 11%, Força 11%  
  Fórmula: `(5×n(marking) + 2×n(positioning) + 1×n(concentration) + 1×n(strength)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Pressão** (`pressing`; posições: todas) — Pressionar e recuperar alto.  
  Atributos: Índice de trabalho 36%, Agressividade 18%, Resistência 18%, Aceleração 9%, Trabalho de equipa 9%, Antecipação 9%  
  Fórmula: `(4×n(work_rate) + 2×n(aggression) + 2×n(stamina) + 1×n(acceleration) + 1×n(teamwork) + 1×n(anticipation)) / 11, com n(a) = (a − 1) / 19 × 100`
- **Movimentação sem bola** (`off_the_ball`; posições: todas) — Desmarcações e ataque ao espaço.  
  Atributos: Sem bola 50%, Antecipação 30%, Aceleração 10%, Decisões 10%  
  Fórmula: `(5×n(off_the_ball) + 3×n(anticipation) + 1×n(acceleration) + 1×n(decisions)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Disciplina tática** (`teamwork`; posições: todas) — Cumprir o plano coletivo.  
  Atributos: Trabalho de equipa 56%, Índice de trabalho 22%, Posicionamento 11%, Decisões 11%  
  Fórmula: `(5×n(teamwork) + 2×n(work_rate) + 1×n(positioning) + 1×n(decisions)) / 9, com n(a) = (a − 1) / 19 × 100`

### Específicas da posição

- **Defesa de remates** (`gk_shot_stopping`; posições: GR) — Parar remates à baliza.  
  Atributos: Reflexos 38%, Um para um 15%, Jogo de mãos 15%, Agilidade 15%, Posicionamento 15%  
  Fórmula: `(5×n(reflexes) + 2×n(one_on_ones) + 2×n(handling) + 2×n(agility) + 2×n(positioning)) / 13, com n(a) = (a − 1) / 19 × 100`
- **Segurança de mãos** (`gk_handling`; posições: GR) — Agarrar sem dar recargas.  
  Atributos: Jogo de mãos 62%, Concentração 25%, Compostura 12%  
  Fórmula: `(5×n(handling) + 2×n(concentration) + 1×n(composure)) / 8, com n(a) = (a − 1) / 19 × 100`
- **Domínio aéreo** (`gk_aerial`; posições: GR) — Sair a cruzamentos e dominar a área.  
  Atributos: Alcance aéreo 40%, Domínio da área 40%, Impulsão 10%, Coragem 10%  
  Fórmula: `(4×n(aerial_reach) + 4×n(command_of_area) + 1×n(jumping_reach) + 1×n(bravery)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Distribuição** (`gk_distribution`; posições: GR) — Repor e iniciar a construção.  
  Atributos: Pontapé 40%, Lançamento 30%, Passe 20%, Visão 10%  
  Fórmula: `(4×n(kicking) + 3×n(throwing) + 2×n(passing) + 1×n(vision)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Saídas da baliza** (`gk_sweeping`; posições: GR) — Jogar fora da área como líbero.  
  Atributos: Saídas 30%, Aceleração 20%, Antecipação 20%, Decisões 20%, Um para um 10%  
  Fórmula: `(3×n(rushing_out) + 2×n(acceleration) + 2×n(anticipation) + 2×n(decisions) + 1×n(one_on_ones)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Comando e comunicação** (`gk_communication`; posições: GR) — Organizar a defesa.  
  Atributos: Comunicação 44%, Domínio da área 22%, Liderança 22%, Concentração 11%  
  Fórmula: `(4×n(communication) + 2×n(command_of_area) + 2×n(leadership) + 1×n(concentration)) / 9, com n(a) = (a − 1) / 19 × 100`
- **Defesa aérea** (`aerial_defending`; posições: DC) — Dominar a própria área pelo ar.  
  Atributos: Cabeceamento 27%, Impulsão 27%, Força 18%, Posicionamento 18%, Coragem 9%  
  Fórmula: `(3×n(heading) + 3×n(jumping_reach) + 2×n(strength) + 2×n(positioning) + 1×n(bravery)) / 11, com n(a) = (a − 1) / 19 × 100`
- **Apoio no corredor** (`flank_support`; posições: DD, DE) — Subir e descer o corredor.  
  Atributos: Resistência 30%, Velocidade 20%, Cruzamentos 20%, Índice de trabalho 20%, Sem bola 10%  
  Fórmula: `(3×n(stamina) + 2×n(pace) + 2×n(crossing) + 2×n(work_rate) + 1×n(off_the_ball)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Proteção da defesa** (`screening`; posições: MDC) — Fechar linhas à frente dos centrais.  
  Atributos: Posicionamento 30%, Antecipação 30%, Desarme 20%, Trabalho de equipa 10%, Concentração 10%  
  Fórmula: `(3×n(positioning) + 3×n(anticipation) + 2×n(tackling) + 1×n(teamwork) + 1×n(concentration)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Ameaça pelos corredores** (`wide_threat`; posições: MD, ME, AD, AE) — Desequilibrar por fora.  
  Atributos: Drible 30%, Aceleração 30%, Cruzamentos 20%, Talento 10%, Sem bola 10%  
  Fórmula: `(3×n(dribbling) + 3×n(acceleration) + 2×n(crossing) + 1×n(flair) + 1×n(off_the_ball)) / 10, com n(a) = (a − 1) / 19 × 100`
- **Ameaça na área** (`box_threat`; posições: PL, MO, AD, AE) — Aparecer e concluir na área.  
  Atributos: Sem bola 27%, Finalização 27%, Antecipação 18%, Compostura 18%, Cabeceamento 9%  
  Fórmula: `(3×n(off_the_ball) + 3×n(finishing) + 2×n(anticipation) + 2×n(composure) + 1×n(heading)) / 11, com n(a) = (a − 1) / 19 × 100`
- **Jogo de costas** (`hold_up`; posições: PL) — Segurar a bola e ligar o jogo.  
  Atributos: Força 30%, Primeiro toque 30%, Equilíbrio 20%, Cabeceamento 10%, Trabalho de equipa 10%  
  Fórmula: `(3×n(strength) + 3×n(first_touch) + 2×n(balance) + 1×n(heading) + 1×n(teamwork)) / 10, com n(a) = (a − 1) / 19 × 100`

## Posições

| Posição | Métricas (quota do peso) |
|---|---|
| GR — Guarda-redes | Defesa de remates 31%, Segurança de mãos 15%, Domínio aéreo 15%, Comando e comunicação 10%, Distribuição 10%, Saídas da baliza 5%, Tomada de decisão 5%, Concentração e regularidade 5%, Frieza 3% |
| DC — Defesa central | Posicionamento defensivo 18%, Marcação 14%, Desarme 14%, Jogo de cabeça 9%, Defesa aérea 9%, Força 7%, Concentração e regularidade 7%, Tomada de decisão 5%, Coragem e agressividade 5%, Velocidade 5%, Passe 4%, Frieza 4% |
| DD — Defesa direito | Desarme 11%, Velocidade 11%, Apoio no corredor 11%, Posicionamento defensivo 9%, Resistência 9%, Marcação 8%, Cruzamento 8%, Ética de trabalho 6%, Pressão 6%, Tomada de decisão 5%, Passe 5%, Drible 4%, Concentração e regularidade 4%, Disciplina tática 4% |
| DE — Defesa esquerdo | Desarme 11%, Velocidade 11%, Apoio no corredor 11%, Posicionamento defensivo 9%, Resistência 9%, Marcação 8%, Cruzamento 8%, Ética de trabalho 6%, Pressão 6%, Tomada de decisão 5%, Passe 5%, Drible 4%, Concentração e regularidade 4%, Disciplina tática 4% |
| MDC — Médio defensivo | Proteção da defesa 17%, Posicionamento defensivo 11%, Desarme 11%, Passe 11%, Tomada de decisão 9%, Disciplina tática 7%, Ética de trabalho 6%, Concentração e regularidade 6%, Frieza 6%, Pressão 5%, Resistência 5%, Força 4%, Controlo de bola 4% |
| MC — Médio centro | Passe 15%, Tomada de decisão 12%, Controlo de bola 10%, Disciplina tática 8%, Ética de trabalho 8%, Resistência 8%, Passe criativo 8%, Movimentação sem bola 6%, Frieza 6%, Desarme 5%, Pressão 5%, Remate de longe 3%, Posicionamento defensivo 3% |
| MD — Médio direito | Ameaça pelos corredores 15%, Cruzamento 14%, Velocidade 10%, Resistência 10%, Ética de trabalho 8%, Drible 8%, Passe 8%, Movimentação sem bola 7%, Disciplina tática 6%, Tomada de decisão 5%, Controlo de bola 5%, Pressão 4% |
| ME — Médio esquerdo | Ameaça pelos corredores 15%, Cruzamento 14%, Velocidade 10%, Resistência 10%, Ética de trabalho 8%, Drible 8%, Passe 8%, Movimentação sem bola 7%, Disciplina tática 6%, Tomada de decisão 5%, Controlo de bola 5%, Pressão 4% |
| MO — Médio ofensivo | Passe criativo 16%, Controlo de bola 12%, Passe 10%, Criatividade 10%, Tomada de decisão 10%, Ameaça na área 8%, Movimentação sem bola 8%, Drible 8%, Remate de longe 6%, Frieza 6%, Agilidade e equilíbrio 4% |
| AD — Extremo direito | Ameaça pelos corredores 16%, Drible 14%, Velocidade 14%, Movimentação sem bola 8%, Controlo de bola 8%, Cruzamento 8%, Criatividade 7%, Finalização 6%, Agilidade e equilíbrio 6%, Tomada de decisão 5%, Ameaça na área 4%, Pressão 4% |
| AE — Extremo esquerdo | Ameaça pelos corredores 16%, Drible 14%, Velocidade 14%, Movimentação sem bola 8%, Controlo de bola 8%, Cruzamento 8%, Criatividade 7%, Finalização 6%, Agilidade e equilíbrio 6%, Tomada de decisão 5%, Ameaça na área 4%, Pressão 4% |
| PL — Ponta de lança | Finalização 22%, Ameaça na área 14%, Movimentação sem bola 12%, Frieza 8%, Controlo de bola 8%, Velocidade 8%, Jogo de cabeça 6%, Jogo de costas 6%, Tomada de decisão 5%, Força 4%, Pressão 4%, Agilidade e equilíbrio 3% |

## Funções táticas

Todas por confirmar no FM27 instalado (`availability: unconfirmed`).

| Função | Posições | Métricas (quota do peso) |
|---|---|---|
| Guarda-redes líbero | GR | Saídas da baliza 20%, Defesa de remates 20%, Distribuição 15%, Controlo de bola 8%, Passe 8%, Domínio aéreo 8%, Tomada de decisão 8%, Frieza 6%, Velocidade 4%, Comando e comunicação 3% |
| Defesa central com bola | DC | Passe 15%, Posicionamento defensivo 14%, Frieza 12%, Marcação 10%, Desarme 10%, Jogo de cabeça 10%, Passe criativo 8%, Controlo de bola 8%, Tomada de decisão 8%, Concentração e regularidade 5% |
| Defesa lateral ofensivo | DD, DE | Apoio no corredor 18%, Cruzamento 14%, Velocidade 12%, Resistência 10%, Drible 8%, Movimentação sem bola 8%, Desarme 8%, Posicionamento defensivo 6%, Ética de trabalho 6%, Disciplina tática 5%, Passe 5% |
| Médio recuperador de bolas | MDC, MC | Desarme 20%, Pressão 18%, Ética de trabalho 12%, Coragem e agressividade 10%, Resistência 10%, Posicionamento defensivo 8%, Disciplina tática 8%, Força 6%, Tomada de decisão 4%, Passe 4% |
| Construtor de jogo recuado | MDC, MC | Passe 22%, Passe criativo 17%, Controlo de bola 13%, Tomada de decisão 13%, Frieza 11%, Disciplina tática 9%, Posicionamento defensivo 9%, Concentração e regularidade 6% |
| Médio área a área | MC | Resistência 14%, Ética de trabalho 14%, Passe 10%, Desarme 10%, Movimentação sem bola 10%, Pressão 8%, Tomada de decisão 8%, Controlo de bola 6%, Remate de longe 6%, Disciplina tática 6%, Finalização 4%, Força 4% |
| Mezzala | MC | Movimentação sem bola 14%, Drible 12%, Passe criativo 12%, Controlo de bola 12%, Passe 10%, Tomada de decisão 8%, Criatividade 8%, Remate de longe 6%, Ética de trabalho 6%, Velocidade 4%, Finalização 4%, Ameaça na área 4% |
| Organizador avançado | MC, MO | Passe criativo 21%, Criatividade 15%, Controlo de bola 14%, Passe 12%, Tomada de decisão 12%, Frieza 8%, Movimentação sem bola 6%, Drible 6%, Agilidade e equilíbrio 4% |
| Extremo invertido | MD, ME, AD, AE | Drible 15%, Passe criativo 12%, Passe 10%, Controlo de bola 10%, Ameaça pelos corredores 10%, Velocidade 10%, Criatividade 8%, Movimentação sem bola 6%, Tomada de decisão 6%, Remate de longe 5%, Cruzamento 4%, Agilidade e equilíbrio 4% |
| Avançado interior | AD, AE | Finalização 15%, Drible 14%, Movimentação sem bola 13%, Velocidade 13%, Ameaça na área 10%, Frieza 8%, Controlo de bola 8%, Agilidade e equilíbrio 6%, Remate de longe 5%, Tomada de decisão 4%, Criatividade 4% |
| Avançado pressionante | PL | Pressão 22%, Ética de trabalho 15%, Resistência 12%, Finalização 10%, Coragem e agressividade 8%, Velocidade 8%, Movimentação sem bola 8%, Disciplina tática 7%, Força 5%, Tomada de decisão 5% |
| Falso nove | PL | Passe criativo 15%, Controlo de bola 15%, Passe 12%, Criatividade 12%, Drible 10%, Tomada de decisão 10%, Movimentação sem bola 8%, Finalização 8%, Frieza 6%, Agilidade e equilíbrio 4% |
| Homem-alvo | PL | Jogo de cabeça 19%, Força 19%, Jogo de costas 17%, Finalização 11%, Coragem e agressividade 9%, Ameaça na área 9%, Controlo de bola 6%, Disciplina tática 6%, Frieza 4% |
