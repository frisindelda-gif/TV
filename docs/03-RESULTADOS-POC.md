# 03 — Resultados da prova de conceito

Esta secção responde às 7 perguntas da etapa 1. O que foi **medido** está separado do que
é **afirmado pelas ferramentas de origem** e do que **ainda não foi testado**.

## Ambiente em que a PoC foi construída

Linux na cloud, **sem FM27 instalado e sem nenhum save real**. Por isso:

- O pipeline completo (conector → validação → SQLite → API → frontend) foi testado com
  uma **carreira de teste sintética** (formato FMSuperScout, marcada `synthetic`).
- O Save Reader foi testado contra as **dataclasses reais do fmsave 0.10.0** (objetos
  construídos em memória) e contra um ficheiro inválido real, mas **não contra um `.fm`
  verdadeiro do FM27**.
- O Live Connector foi testado com dumps no formato do `Dumper.cs`, **não com uma leitura
  real da memória**.

O teste de aceitação em Windows com o jogo real (secção 7) é o primeiro passo da próxima etapa.

---

## 1. É tecnicamente possível cumprir os requisitos?

**Sim, com ressalvas.**

| Requisito | Possível? | Como |
|---|---|---|
| Todos os jogadores carregados, incl. regens e desconhecidos | Sim | Ambas as fontes leem a base de dados inteira, independentemente do conhecimento do scout |
| CA / PA | Sim | Memória e save. No save, o PA pode vir como código de intervalo (negativo) |
| Atributos técnicos, mentais, físicos | Sim | 47 + 5 escondidos = 52, nas duas fontes |
| Atributos escondidos | Sim | 5 escondidos + 8 de personalidade, nas duas fontes |
| Posições | Sim | Save: classificação 1–20 nas 15 posições; Live: só listas |
| Funções (roles) | **Não diretamente** | Nenhuma fonte as guarda; terão de ser calculadas por nós (marcadas `derived`) |
| Estatísticas individuais | Sim, **só pelo save** | `player_season_stats`, histórico, por jogo |
| Contratos, salários, valores | Sim | Valor real do FM quando existe; caso contrário `NULL` |
| Informação dos clubes | Parcial | Nome, reputação, (save) Unique ID, posição na liga; divisão só no Live |
| Histórico de evolução | Sim | Construído por nós: um snapshot por importação |
| Live sem escrever na memória | Sim | O scanner pede só `PROCESS_VM_READ` |
| Save sem modificar o ficheiro | Sim | Lemos uma cópia; testado (sha256 e mtime inalterados) |

As ressalvas estão na secção 7: o FM27 sai a 10-11-2026, e o fmsave ainda não confirmou
nenhum campo de jogador contra o FM27.

## 2. Melhor mecanismo de leitura

**Os dois, com papéis diferentes — e a fonte principal de verdade deve ser o save.**

- **Save Reader (fmsave)** como fonte principal: mais campos (estatísticas, classificações por
  posição, pés, contrato completo), API Python pública, não depende de o jogo estar aberto,
  reprodutível (o ficheiro pode ser reimportado).
- **Live Connector (scanner FMSuperScout)** para atualizações rápidas durante o jogo (F9 /
  botão), sem gravar; e como **segunda leitura independente** para verificar CA/PA/atributos
  do save (o autor do FMSuperScout verificou os campos contra um FM27 a correr).
- Reimplementar a leitura de memória em Python **não** é recomendado nesta fase.

## 3. Quantos jogadores conseguimos importar?

Medido nesta PoC (dados sintéticos, mesmo formato e volume reais):

| Volume | Carregar + normalizar | Gravar | Integridade | BD |
|---|---|---|---|---|
| 60 000 jogadores | 4,3 s | 5,3 s | 1,3 s | 65 MB |

Limite prático: nenhum limite no código; o custo cresce linearmente (estimativa, não
medida: ~600k jogadores ≈ 1–2 min e ~650 MB por importação).

Afirmado pelas ferramentas (não medido por nós): FMSuperScout lê "60 000+ jogadores e staff"
numa base normal e 635k pessoas numa base muito grande; a documentação do fmsave mostra um
save com 124 310 jogadores.

## 4. Campos que conseguimos extrair

`✓` = implementado na PoC · `—` = a fonte não fornece

| Campo | Live (memória) | Save (fmsave) |
|---|---|---|
| Unique ID, nome | ✓ | ✓ (+ primeiro/último/comum) |
| Data de nascimento | ✓ (derivada de ano + dia) | ✓ |
| Idade, altura | ✓ | ✓ |
| Nacionalidades (nomes) | ✓ | — (só ids) |
| CA | ✓ | ✓ |
| PA | ✓ | ✓ ou código de intervalo |
| 14 técnicos, 14 mentais, 8 físicos, 11 GR | ✓ | ✓ |
| 5 escondidos | ✓ | ✓ |
| 8 personalidade | ✓ | ✓ |
| Classificação 1–20 por posição | — | ✓ |
| Posições naturais / competentes | ✓ | ✓ |
| Pé esquerdo / direito (1–20) | — (só preferido) | ✓ |
| Reputação casa / atual | — | ✓ |
| Reputação mundial | ✓ | ✓ |
| Clube (nome, reputação) | ✓ | ✓ |
| Divisão | ✓ | — (requer mapa de nomes) |
| Empréstimo / clube dono | ✓ | ✓ (+ fim do empréstimo) |
| Salário semanal, fim de contrato | ✓ | ✓ |
| Início de contrato, estatuto no plantel | — | ✓ |
| Listado / intransferível / dispensa | ✓ | — (não exposto na 0.10) |
| Valor de transferência do FM | ✓ (null se o FM não guarda) | ✓ (com estado) |
| Traços | — | ✓ (parcialmente nomeados) |
| Estatísticas da época | — | ✓ |
| Data do jogo | ✓ (às vezes adiantada) | ✓ |

## 5. Campos não disponíveis

- **Funções (roles) e a sua classificação:** nenhuma fonte; teriam de ser calculadas.
- **Preço pedido real:** o FM calcula-o por negociação; não está guardado (ambos confirmam).
- **Exigência salarial:** não guardada.
- **Nomes de nações/competições no save:** vêm da BD instalada, não do save.
- **Estatísticas no Live:** não lidas pelo scanner.
- **Conhecimento do scout / relatórios de scouting:** nenhuma das ferramentas os expõe.
- **Atributos "potenciais" por atributo:** não existem no jogo; qualquer projeção seria estimativa.

## 6. Arquitetura final recomendada

Ver [`02-ARQUITETURA.md`](02-ARQUITETURA.md): dois conectores independentes → contrato
normalizado com estado por campo → validação → SQLite (identidade + snapshots + tabela larga
de atributos) → FastAPI local → React. Próximo componente: verificação cruzada Live × Save.

## 7. Limitações a resolver antes de avançar

1. **Teste com o jogo real (bloqueante).** Em Windows, com FM27:
   - instalar o FMSuperScout (ou compilar o scanner), carregar um save, correr
     `fm27si import-live --scan "C:\...\FMSuperScout.Scanner.exe"`;
   - gravar o jogo nessa mesma data e correr `fm27si import-save "...\save.fm"`;
   - `set FM27SI_REAL_SAVE=...\save.fm` e `pytest` (ativa o teste com save real);
   - comparar 10–20 jogadores com o ecrã do jogo e entre as duas fontes.
2. **Patch de lançamento do FM27 (10-11-2026).** Offsets do scanner e layouts do fmsave
   podem mudar. Fixar versões, detetar a versão do jogo e recusar/avisar quando não suportada.
3. **Campos de jogador "unconfirmed" no fmsave para FM27.** Precisamos da verificação cruzada
   (ponto 1) antes de tratar CA/PA do save como fiáveis.
4. **Formato do `dump.json` não é contrato público.** Fixar a versão do FMSuperScout e manter
   testes de contrato; acompanhar releases.
5. **Identificação da carreira.** A heurística confunde carreiras com o mesmo nome de
   manager; a UI deve pedir/confirmar a `career_key`.
6. **Crescimento da BD.** ~65 MB por importação de 60k jogadores: definir retenção (p.ex.
   manter todas as importações de save, e só uma leitura live por semana de jogo) ou
   guardar apenas diferenças.
7. **Nomes em falta no Save Reader** (nações, divisões): preencher a partir do Live por
   Unique ID ou de um CSV `database_id → nome` do utilizador.
8. **Funções (roles):** decidir um modelo de cálculo, sempre marcado `derived`.
9. **Staff** não é importado na PoC (ambas as fontes o suportam).
10. **Termos de uso:** ambas as ferramentas destinam-se a uso pessoal em single-player;
    manter a app estritamente local e pessoal.

## Testes da PoC

`cd backend && pytest` → **47 passam, 1 ignorado** (o teste com save real, que precisa de
`FM27SI_REAL_SAVE`). Cobrem:

- validação de CA, PA, códigos de PA, atributos (intervalo, escala editada, chaves
  desconhecidas, completude, bloco constante), posições;
- mapeamento completo do Live (52 + 8 atributos, empréstimo, valor em falta = `NULL`,
  versão não verificada, registo corrompido, ficheiro de origem inalterado);
- mapeamento do Save contra as dataclasses reais do fmsave, leitura da cópia, ficheiro
  intacto, leitor opcional a falhar = aviso, ficheiro inválido real rejeitado;
- integridade: contagens origem = BD, idempotência por sha256, histórico de 3 épocas com
  regens e retirados, valores preservados exatamente, registo inválido guardado e
  sinalizado, Unique ID duplicado, Unique ID reutilizado, separação de carreiras;
- API: listagem, filtros (idade, PA, atributos, posição), perfil completo com proveniência
  e histórico, relatório de integridade, erros 404/422.
