# Decisões técnicas (registo)

Formato curto: contexto → decisão → consequências. Uma decisão só muda com uma nova entrada.

## D-01 — Backend Python/FastAPI + SQLite, tudo local
- **Decisão:** API em `127.0.0.1`, base SQLite em `%LOCALAPPDATA%\FM27ScoutingIntelligence`
  (configurável por `FM27SI_DATA_DIR`). Sem serviços cloud; nenhum pedido de rede de saída.
- **Consequências:** instalação simples em Windows; um único escritor (importações
  serializadas por lock).

## D-02 — Live Connector reutiliza o scanner do FMSuperScout (não reimplementar)
- **Contexto:** ler a memória exige offsets por versão que alguém tem de manter após cada
  patch. O FMSuperScout já o faz, é MIT, abre o processo só com permissões de leitura.
- **Decisão:** invocar `FMSuperScout.Scanner.exe scan` (opcional, a pedido) e ler
  `dump.json` em modo só-leitura. Mapeamento fixado contra o formato 1.7.x, com validação.
- **Consequências:** zero escrita na memória do FM pelo nosso código; dependência de um
  formato JSON interno não versionado → testes de contrato e verificação de `meta.game` /
  `versionOk`. Se o projeto morrer, plano B: portar `MemScan` para Python.

## D-03 — Save Reader usa o fmsave como dependência fixada
- **Decisão:** `fmsave==0.10.0` (extra `save`). O ficheiro é copiado para uma pasta temporária
  e só a cópia é lida.
- **Consequências:** atualizar o fmsave é uma decisão consciente (o layout FM27 muda entre
  versões); os testes do adaptador usam as dataclasses reais do fmsave e falham se a API
  mudar.

## D-04 — Contrato normalizado único (`fm27si/schemas.py`)
- Ambos os conectores produzem `ImportBundle`. O importador não conhece formatos de origem.
- Cada campo tem um estado: `verified` / `unconfirmed` / `derived` / `estimate`. A PoC não
  produz estimativas; valores em falta ficam `NULL`.

## D-05 — Identidade = (carreira, Unique ID do FM); histórico = snapshots
- `players` guarda identidade estável; cada importação cria `player_snapshots`.
- O FM pode reutilizar o Unique ID de uma pessoa apagada: data de nascimento diferente ⇒
  nova identidade (com aviso).
- O Unique ID é o mesmo nas duas fontes, o que permite cruzar memória e save.

## D-06 — Atributos numa tabela larga
- Primeira versão: tabela chave/valor (3,6 M linhas por 60k jogadores, 50 s, 362 MB).
- Decisão: `snapshot_attributes` com uma coluna por atributo (60), uma linha por snapshot.
  Resultado medido: ~10 s e 65 MB para 60k jogadores; filtros como `pace >= 15` são
  `WHERE` simples.

## D-07 — Validação não corrige
- Problemas vão para `validation_issues`; o snapshot fica com `quality = ok|warning|error`.
  Valores impossíveis (CA 0, PA 250) são guardados tal como lidos e sinalizados — sinal de
  offset/layout errado que não deve ser escondido.

## D-08 — Idempotência por sha256
- O mesmo ficheiro na mesma carreira não gera nova importação.

## D-09 — Carreira identificada heuristicamente, com chave explícita disponível
- Chave automática: `jogo|manager|save_name ou clube`. Como o utilizador usa normalmente o
  mesmo nome de manager em várias carreiras, a chave explícita `career_key` é a forma
  fiável; há aviso quando menos de 50 % dos jogadores coincidem com a importação anterior.

## D-10 — Carreira de teste sintética
- Não existe (nem pode ser publicado) um save real neste repositório. O gerador
  `fm27si/testdata.py` produz dumps no formato FMSuperScout marcados `synthetic: true`;
  tudo o que vem daí fica marcado na BD (`import_runs.synthetic`).

## D-11 — Avaliação como dados, motor separado
- Métricas, posições e funções são uma especificação validada (JSON), não código. O motor
  é puro (sem BD/HTTP) e o mesmo cálculo serve um jogador ou o lote inteiro.
- Métricas referem atributos; posições e funções referem métricas (sem duplicar atributos).

## D-12 — Dados em falta nunca são zero
- Média ponderada só sobre o disponível + cobertura; abaixo do mínimo não se calcula.

## D-13 — Modelo original imutável, versões identificadas por hash
- O original só se altera numa nova versão da app; o utilizador trabalha em cópias.
- `spec_hash` em cada avaliação garante reprodutibilidade e deteta rankings desatualizados.

## D-14 — Funções só as pedidas, todas por confirmar
- Não é possível ler a lista de funções do FM27 instalado; incluem-se apenas as 13 pedidas,
  marcadas `unconfirmed`, desativáveis no Lab.

## D-15 — numpy para o motor
- 60 000 jogadores em ~0,6 s; sem numpy seriam dezenas de segundos por recálculo.
