# 01 — Investigação técnica: FMSuperScout e fmsave

Data da análise: 7 de novembro de 2026. Código lido diretamente dos repositórios (não da
documentação apenas):

| Projeto | Commit analisado | Versão |
|---|---|---|
| [mavarobli/FMSuperScout](https://github.com/mavarobli/FMSuperScout) | `09bcc62` (2026-11-07) | 1.7.3 |
| [rhiever/fmsave](https://github.com/rhiever/fmsave) | `24885eb` (2026-11-06) | 0.10.0 (PyPI) |

> Contexto importante: segundo o próprio backlog do FMSuperScout (`docs/backlog.md`), o
> lançamento do FM27 é a **10 de novembro de 2026**. Ambas as ferramentas estão afinadas
> para a build 27.0 disponível antes do lançamento (fmsave: `27.0.0+2486695`). O patch do dia
> de lançamento pode deslocar offsets/layouts.

---

## 1. FMSuperScout

### 1.1 Como funciona tecnicamente

- **Leitura de memória externa (Windows).** `scanner/Program.cs` + `core/MemScan.Win.cs`:
  um executável C#/.NET 8 abre `fm.exe` com `OpenProcess(PROCESS_VM_READ |
  PROCESS_QUERY_INFORMATION)` — só leitura — e usa `VirtualQueryEx` + `ReadProcessMemory`.
  Não injeta nada no jogo e não usa mod loader (o antigo plugin BepInEx de FM26 foi
  abandonado).
- **Descoberta dos objetos.** Percorre as regiões privadas `MEM_COMMIT`/`PAGE_READWRITE` do
  heap à procura de ponteiros de vtable que caem dentro de `game_plugin.dll` (a base de
  dados nativa C++) / `GameAssembly.dll`. Classifica cada objeto (jogador, staff, manager,
  clube) por offsets dinâmicos (`core/MemScan.cs`, `core/Dumper.cs`).
- **Leitura dos campos por offsets fixos por versão** (`core/Fields.cs`). As offsets de FM26
  vêm das tabelas Cheat Engine de "tdg6661" (26.3.x); o layout FM27 foi derivado e
  "re-verificado por campo contra um FM 27.0 a correr" (02-11-2026). Só uma offset mudou
  (`HUMAN_MANAGER_OFFSET`).
- **Opcional: VA clone** (`PssCaptureSnapshot`) para uma fotografia consistente da memória —
  continua a ser só leitura, mas custa memória e abranda o FM; é apenas uma "segunda
  tentativa".
- **macOS:** rota diferente — um módulo NativeAOT carregado *dentro* do processo do FM
  (o FM tem de ser lançado pela app). Fora do âmbito (queremos Windows).
- **Saída:** `%LOCALAPPDATA%\FMSuperScout\dump.json` (+ `status.json`, `diagnostics.txt`,
  `scanner.log`). Disparo: `FMSuperScout.Scanner.exe scan` (uma leitura) ou `watch`
  (F9 no jogo / ficheiro `request.flag`). A app de visualização é Node puro (`app/server.js`).

### 1.2 Dados que extrai do FM27 (confirmado em `Dumper.WritePerson`)

Jogadores: `id` (Unique ID), nome, idade, ano + dia-do-ano de nascimento, nacionalidades
(nomes) + id, clube atual, clube dono (empréstimo), divisão, género (só se feminino),
**CA, PA**, salário semanal, fim de contrato, posições (lista "natural" e "≥15"), tipo de
equipa (principal/reservas/juniores), pé preferido (texto), altura, **valor de transferência
real do FM** (null quando o FM não guarda), estado de transferência (listado, empréstimo,
intransferível, dispensa), transferência acordada (clube + data), reputação do clube,
reputação mundial, **8 atributos de personalidade escondidos**, **47 atributos visíveis +
5 escondidos** (Consistency, Dirtiness, ImportantMatches, InjuryProneness, Versatility).

Staff: CA/PA, atributos de staff, função, preferência de função, reputações, personalidade.

Meta: data do jogo (lida da memória ou derivada), versão do jogo, versão suportada, flag
`versionOk`, nome do manager, clube do utilizador, moeda (GBP).

**Não extrai:** estatísticas de jogo/época, classificação 1–20 por posição (lida
internamente, mas só sai a lista), pés esquerdo/direito numéricos, IDs de clube, traços,
funções (roles), data de início de contrato, estatuto no plantel.

### 1.3 Como obtém CA, PA e atributos escondidos

- CA/PA: dois `u16` no bloco do jogador (`PLAO_CA = 0x264`, `PLAO_PA = 0x266`).
- Atributos: bloco de 55 bytes em `PLAO_ATTRS = 0x15F`, guardados ×5 (escala 1–100),
  convertidos para 1–20 com arredondamento (`Attr()` → `floor(raw/5 + 0.5)`). Os escondidos
  estão no mesmo bloco (offsets 0x29, 0x2C, 0x2F, 0x30, 0x31).
- Personalidade: bytes 1–20 no bloco da pessoa (`PERO_ADAPTABILITY = 0x70` … `0x77`).

### 1.4 Interfaces / formatos reutilizáveis

- **Não existe API.** Confirmado: nenhuma biblioteca, nenhum endpoint estável; o servidor
  Node (`app/server.js`) é só para a app deles.
- **Reutilizável na prática:** o executável `FMSuperScout.Scanner.exe scan` (processo
  externo) e o ficheiro `dump.json`. O formato **não está versionado** nem documentado como
  contrato público — muda com o código.

### 1.5 Integração no nosso backend

Possível e implementada na PoC como **processo externo + leitura do JSON**
(`fm27si/connectors/live_fmsuperscout.py`). Alternativa futura: portar `MemScan`/`Fields`
para Python (`ctypes` + `ReadProcessMemory`) — ~2 500 linhas C# e, sobretudo, a
responsabilidade de voltar a fixar offsets após cada patch. Não recomendado nesta fase.

### 1.6 Licença

**MIT** (Copyright (c) 2026 mavarobli). Permite uso, modificação e redistribuição, incluindo
privada, com a condição de manter o aviso de copyright e a licença em cópias substanciais.
Não copiamos código; invocamos o executável. Sem garantia. O projeto declara "single-player
use only" e não afiliação à Sports Interactive/SEGA.

### 1.7 Limitações na versão atual do FM27

- Offsets fixadas a **game_plugin 27.0**; versão diferente → aviso âmbar e possíveis dados
  lixo até nova versão (`docs/repin-guide.md`). O lançamento oficial (10-11-2026) é um ponto
  de risco declarado no backlog deles.
- Data do jogo vem do próximo jogo da equipa: em pausas pode estar até duas semanas adiantada.
- Bit "loan listed" não verificado (comentário no `Dumper.cs`).
- Valor de mercado: lido da memória para a maioria; para os restantes a app deles *estima*
  (no `app.js`, não no dump) — o dump fica `null`, o que é o que queremos.
- FM a correr como administrador impede a leitura.
- Mac: apenas versão Steam, e o FM tem de ser lançado pela app.

---

## 2. fmsave

### 2.1 Como funciona tecnicamente

- Biblioteca **Python pura** (≥ 3.12), dependência única `backports.zstd` (< 3.14).
- Lê o contentor `.fm` (secções comprimidas zstd), descodifica a base de dados do jogo e
  devolve dataclasses imutáveis em `Table`s. Layouts por build (`_layouts/fm27_27_0_0.py`);
  builds FM27 desconhecidas "emprestam" o layout por secção quando o schema coincide.
- **Só leitura, sem rede, não lê memória.** Recomenda ler uma cópia se o jogo estiver aberto.
- Verificações (`_checks.py`): completude, joins e intervalos esperados. **No FM27, uma
  verificação falhada pára sempre o leitor**, mesmo com `strict=False`.

### 2.2 Dados que extrai do FM27

30 leitores. Para scouting interessam: `players()` (nomes, nascimento, idade, nação (id),
altura, **CA, PA ou código de intervalo de PA**, reputação casa/atual/mundial, clube,
**52 atributos** em escala 1–20 e bruta 1–100, **8 de personalidade**, **15 classificações
de posição**, pé esquerdo/direito, valor de transferência + estado, traços (parcialmente
nomeados), empréstimo, contrato, castigos), `contracts()` (salário, datas, estatuto no
plantel, cláusulas), `clubs()`, `player_season_stats()` (época atual, por tipo de competição:
jogos, minutos, golos, assistências, xG, xA, nota média, passes, desarmes, …),
`player_season_history()`, `player_match_stats()`, `staff()`, `nations()`, `competitions()`,
`finances()`, etc.

### 2.3 CA, PA e escondidos

Lidos do registo do jogador no save: `Player.ability.current/potential`,
`potential_range_code` quando o save guarda um PA negativo (intervalo) em vez de valor fixo;
`Player.attributes` inclui os 5 escondidos; `Player.personality` os 8 de personalidade.

### 2.4 Interfaces reutilizáveis

- **API Python pública e documentada:** `fmsave.open(path)` → `Save.players()`, …;
  `Table.to_dicts()/to_pandas()/write_json()`; `fmsave.field_status(...)`;
  `fmsave.validate_save(...)`.
- **CLI:** `fmsave export SAVE players --all -o players.jsonl`, `fmsave validate SAVE --json`.

### 2.5 Integração

Direta: dependência Python fixada (`fmsave==0.10.0`) chamada pelo nosso
`fm27si/connectors/save_fmsave.py`. Sem cópia de código.

### 2.6 Licença

**MIT** (Copyright (c) 2026 Randal S. Olson). Mesmas condições. O autor **não aceita pull
requests** (só issues) e pede que nunca se publiquem saves.

### 2.7 Limitações no FM27

- **Nenhum campo de jogador está "verified" no FM27.** A lista `_FM27_VERIFIED_FIELDS`
  contém apenas campos de staff; os rótulos globais descrevem o FM26. Ou seja, CA, PA e
  atributos lidos de um save FM27 são, segundo a própria biblioteca, **"unconfirmed"**.
- Nomes vindos da BD instalada do jogo **não estão no save**: nações, competições, cidades
  (só ids; é preciso um mapa externo).
- Dinheiro na unidade interna do save, sem conversão para a moeda mostrada.
- Três campos de estatísticas de época não são lidos no FM27; cobertura de histórico varia.
- Build FM27 diferente de `27.0.0+2486695` → "unverified build"; secção com schema diferente
  → `UnsupportedGameError` só nesse leitor.

---

## 3. Comparação direta

| Critério | FMSuperScout (memória) | fmsave (ficheiro .fm) |
|---|---|---|
| Linguagem / integração | C# exe externo + JSON | Python, import direto |
| Precisa do FM aberto | Sim | Não |
| Precisa de gravar o jogo | Não | Sim |
| Velocidade anunciada | ~6 s para 60k pessoas | não medido aqui (sem save real) |
| CA / PA | Sim (verificado pelo autor no 27.0) | Sim (unconfirmed no FM27) |
| 52 atributos + 8 personalidade | Sim | Sim |
| Classificação 1–20 por posição | Não (só listas) | Sim |
| Estatísticas | **Não** | **Sim** (época, histórico, jogo) |
| Contrato | salário, fim, estado de transferência | salário, início, fim, estatuto, cláusulas |
| Nomes de nações/competições | Sim | Não (só ids) |
| Formato estável | Não (JSON interno) | API pública versionada |
| Risco de patch | Offsets de memória | Layouts do save |
| Licença | MIT | MIT |
