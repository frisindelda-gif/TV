# 04 — Interface (v1)

Servida pelo próprio backend em `http://127.0.0.1:8727/` (após `npm run build`), ou em modo
de desenvolvimento pelo Vite em `http://127.0.0.1:5173/` (com proxy para a API).

## Ecrãs

### Jogadores (`/jogadores`)
- Tabela ordenável: nome, idade, posições (naturais a negrito), nacionalidade, clube, CA, PA,
  valor, salário semanal, fim de contrato, qualidade da leitura.
- Filtros: nome, posição, clube, nacionalidade, idade mín./máx., CA mín., PA mín., valor
  máx., fim de contrato, e qualquer número de **filtros de atributo** (p.ex. Velocidade ≥ 16),
  incluindo escondidos e personalidade.
- Filtros rápidos: Wonderkids (≤19, PA ≥150), Potencial barato (≤23, PA ≥140, ≤ £2M),
  Contrato a terminar (até 1 ano após a data do jogo), Elite (CA ≥150), Leituras com erro.
- Os filtros ficam no endereço da página: voltar do perfil mantém a pesquisa, e uma pesquisa
  pode ser guardada como marcador do browser.
- Em ecrãs pequenos os filtros ficam recolhidos atrás de um botão.

### Perfil (`/jogador/:id`)
- Cabeçalho: idade, nascimento, nacionalidades, altura, pé, clube, divisão, posições; CA e PA
  com o estado de confiança (verificado / não confirmado / derivado / estimativa).
- Valor, salário, contrato, reputações, Unique ID.
- Atributos técnicos, mentais e físicos (guarda-redes: GR, mentais, físicos + técnicos por
  baixo), com a escala de cores 1–5 / 6–10 / 11–15 / 16–20.
- Atributos escondidos e personalidade.
- Campo com as posições (classificação 1–20 quando a fonte a tem).
- Contrato completo, empréstimo, situação de transferência, traços.
- Evolução: gráficos de CA/PA e de valor por importação + tabela com a variação de CA.
- Estatísticas da época (quando importadas do save).
- Origem e fiabilidade: fonte, ferramenta, ficheiro, datas, estado de cada campo, problemas
  de leitura e campos que a fonte não fornece.
- Seletor para ver o jogador como estava numa importação anterior.

### Dados (`/dados`)
- Nome da carreira (chave explícita, recomendada).
- Importar save `.fm` (caminho do ficheiro).
- Ler o jogo: opcionalmente corre o scanner do FMSuperScout e importa o `dump.json`.
- Criar carreira de demonstração (400 jogadores, 3 épocas, marcada como sintética).
- Lista de importações da carreira, com relatório de integridade (verificações, cobertura,
  ficheiro, avisos).

### Geral
- Seletor de carreira no topo; barra com a última importação, data no jogo, época, número
  de jogadores e aviso de dados sintéticos ou versão do jogo não verificada.
- Tema claro/escuro.

## Ainda não incluído
Shortlists, comparação de jogadores, funções (roles), staff, exportação CSV, análise de
plantel. Ficam para a próxima etapa, de preferência depois do teste com o FM27 real.
