# FM27 Scouting Intelligence

Aplicação web **local e pessoal** para scouting no Football Manager 2027.

Etapa atual: **interface v1** sobre a prova de conceito. Funciona de ponta a ponta com a
carreira de demonstração (dados sintéticos); a leitura do FM27 real ainda não foi testada
(ver [`docs/03-RESULTADOS-POC.md`](docs/03-RESULTADOS-POC.md), secção 7).

- Interface: [`docs/04-INTERFACE.md`](docs/04-INTERFACE.md)
- Métricas: [`docs/05-METRICAS.md`](docs/05-METRICAS.md)
- Statistical Scouting: [`docs/08-STATISTICAL-SCOUTING.md`](docs/08-STATISTICAL-SCOUTING.md)
- Avaliação por posição e função: [`docs/06-AVALIACAO.md`](docs/06-AVALIACAO.md) · pesos: [`docs/07-PESOS.md`](docs/07-PESOS.md)

- Investigação dos projetos FMSuperScout e fmsave: [`docs/01-INVESTIGACAO.md`](docs/01-INVESTIGACAO.md)
- Arquitetura: [`docs/02-ARQUITETURA.md`](docs/02-ARQUITETURA.md)
- Resultados e limitações: [`docs/03-RESULTADOS-POC.md`](docs/03-RESULTADOS-POC.md)
- Decisões técnicas: [`docs/DECISOES.md`](docs/DECISOES.md)

## Princípios

- Corre só no teu PC (`127.0.0.1`). Sem cloud, sem envio de saves ou dados.
- Nunca escreve na memória do FM27 nem modifica saves (lê uma cópia do `.fm`).
- Nunca inventa dados: o que a fonte não fornece fica vazio; cada campo tem um estado
  (`verified` / `unconfirmed` / `derived` / `estimate`).
- Cada importação regista a origem, o ficheiro (sha256) e as datas (real e no jogo).

## Instalação rápida (Windows)

Requisitos: [Python 3.12+](https://www.python.org/downloads/) e [Node.js 20+](https://nodejs.org/).

1. Duplo clique em **`instalar.cmd`** (só da primeira vez e depois de cada atualização).
2. Duplo clique em **`Iniciar FM27 Scouting.cmd`** — abre `http://127.0.0.1:8727/` no browser.
3. Em **Dados**, importe o seu save, leia o jogo, ou crie a carreira de demonstração.

## Instalação para desenvolvimento (PowerShell)

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[save,dev]"
.venv\Scripts\pytest                      # testes
.venv\Scripts\fm27si serve                # API em http://127.0.0.1:8727/docs

cd ..\frontend
npm install
npm run dev                               # http://127.0.0.1:5173
```

## Importar dados

```powershell
# Carreira de teste SINTÉTICA (não são dados do jogo)
fm27si make-test-career .\testcareer --players 300 --seasons 2
fm27si import-live .\testcareer\dump-season1.json
fm27si import-live .\testcareer\dump-season2.json

# Save Reader: ficheiro .fm (via fmsave)
fm27si import-save "$env:USERPROFILE\Documents\Sports Interactive\Football Manager 27\games\carreira.fm" --career-key minha-carreira

# Live Connector: memória via scanner FMSuperScout (FM27 aberto com o save carregado)
fm27si import-live --scan "C:\Program Files\FMSuperScout\FMSuperScout.Scanner.exe" --career-key minha-carreira

fm27si integrity 1                        # relatório de integridade da importação 1
```

Variáveis opcionais: `FM27SI_DATA_DIR` (pasta da BD), `FM27SI_FMSS_DUMP` (caminho do
`dump.json`), `FM27SI_FMSS_SCANNER` (caminho do scanner), `FM27SI_REAL_SAVE` (ativa o teste
com um save real).

## Estrutura

```
backend/   FastAPI + SQLAlchemy + Pydantic (pacote fm27si) e testes
frontend/  React + TypeScript + Tailwind + shadcn/ui + Recharts (página de verificação)
docs/      investigação, arquitetura, decisões, resultados
```

## Terceiros

Ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Não afiliado à Sports Interactive
nem à SEGA. Football Manager é marca registada dos respetivos titulares.
