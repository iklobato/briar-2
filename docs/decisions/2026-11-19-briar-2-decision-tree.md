# Árvore de decisões — briar-2

Data: 2026-11-19
Projeto: `~/briar-2`
Objetivo: Slim-down do briar CLI em um novo projeto com core `extract + serve`, multi-tenant, eventos e triggers configuráveis.

---

## Como ler este documento

Cada nó tem:
- **Decisão**: a pergunta
- **Por que importa**: impacto técnico/produto
- **Depende de**: decisões que precisam estar respondidas primeiro
- **Fonte**: se eu posso consultar o códigobase atual para responder, ou se VOCÊ precisa decidir

Decisões marcadas **(perguntar)** precisam ser respondidas pelo usuário.
Decisões marcadas **(consultar)** eu posso responder lendo o código existente.

---

## Rodada 1 — Decisões de nível mais alto (7 perguntas)

Estas são as que bloqueiam tudo o mais. Sem respondê-las, não faz sentido aprofundar.

```
R1-01. O que é "extract" no briar-2?
│
├── R1-01a. Quais extractors fazem parte do core?
│   (manter todos os 23, só os 10 originais, só JIT, customizável)
│
├── R1-01b. Quais providers entram no v1?
│   (github, bitbucket, jira, linear, fireflies, aws/gcp/azure — ou subconjunto)
│
└── R1-01c. Cadência: scheduled, on-demand, ou ambos?
    (hoje: scheduled via runbook + on-demand via CLI)

R1-02. O que é "serve" no briar-2?
│
├── R1-02a. Serve é só o scheduler de extração?
│   (hoje: scheduler long-running que também roda agent flows)
│
├── R1-02b. O agent loop (prfix/implement) entra?
│   (hoje: briar agent é um fluxo autônomo com LLM)
│
├── R1-02c. O plan (briar plan) entra?
│   (hoje: board → cards → selector → run loop)
│
└── R1-02d. O dashboard (briar dashboard) entra?
    (hoje: HTML status page)

R1-03. Quais fontes de evento fazem parte do v1?
│
├── R1-03a. Code review events (PR/MR comments, CI status)
│   (fonte: github, bitbucket)
│
├── R1-03b. Slack events (threads, mensagens, reações)
│   (fonte: fireflies + slack webhook)
│
├── R1-03c. Tracker events (ticket created/updated, status moves)
│   (fonte: jira, github-issues, linear)
│
├── R1-03d. Infra events (deployments, alerts, custo)
│   (fonte: aws/gcp/azure, github-deployments)
│
└── R1-03e. Meeting events (standups, decisões, action items)
    (fonte: fireflies transcripts)

R1-04. Modelo de execução do serve
│
├── R1-04a. CLI-only (executado via cron/manualmente)
│
├── R1-04b. Long-running daemon (como o serve atual)
│
├── R1-04c. Server/HTTP (exposto como API)
│
├── R1-04d. Container-first (Docker, orquestrado externamente)
│
└── R1-04e. Serverless (function-as-a-service)

R1-05. Modelo de configuração multi-tenant
│
├── R1-05a. YAML por empresa (como hoje)
│
├── R1-05b. Arquivo de config por empresa (TOML/YAML separado)
│
├── R1-05c. Config centralizada em banco (Postgres/Vault)
│
├── R1-05d. Config como código (git-tracked, PR-based onboarding)
│
└── R1-05e. Híbrido (YAML para extração, secrets no vault/env)

R1-06. O que significa "trigger next steps"
│
├── R1-06a. Quais ações o sistema pode tomar sozinho?
│   (comentar ticket/PR, mover status, criar branch, abrir PR, pedir review,
│    enviar mensagem Slack/Telegram, atualizar infra, criar card em board)
│
├── R1-06b. Níveis de autonomia
│   (sugestão-only, auto-comentar, auto-mudar-status, auto-implementar)
│
├── R1-06c. Quem aprova antes de ações destrutivas?
│   (nenhum, human checkpoint, board-based approval)
│
└── R1-06d. Notificações de resultado
    (Slack, email, PagerDuty, status file, nenhuma)

R1-07. LLM: obrigatório, opcional, ou por feature?
│
├── R1-07a. Obrigatório para tudo (hoje)
│
├── R1-07b. Opcional — extração funciona sem, serve precisa
│
├── R1-07c. Por feature — extração sem, agent/plan com, triggers sem
│
└── R1-07d. Nunca (briar-2 é só coleta + agendamento, sem IA)
```

---

## Rodada 2 — Decididas dependem da Rodada 1 (10 perguntas)

Essas destravam assim que a Rodada 1 tem resposta suficiente. Eu listo as
combinações mais comuns; se a sua escolha na R1 for incomum, eu adapto.

```
R2-01. Stack de deploy do serve
│
├── R2-01a. systemd unit (como hoje, Mac/Debian)
├── R2-01b. Docker Compose (um serviço por company)
├── R2-01c. Kubernetes (Deployment + CronJob)
├── R2-01d. Sem servidor — CLI-only via cron/launchd/GitHub Actions
└── R2-01e. Processo único gerenciado pelo usuário (--foreground)

R2-02. Backend de persistência do knowledge store
│
├── R2-02a. File only (markdown em disco)
├── R2-02b. Postgres only
├── R2-02c. Ambos (file para dev, Postgres para multi-leitor)
└── R2-02d. Outro (SQLite, S3, Redis?)

R2-03. Modelo de entrega de eventos
│
├── R2-03a. Pull-only (polling, como o scheduler hoje)
├── R2-03b. Push via webhooks (GitHub, Slack, Jira)
├── R2-03c. Híbrido — webhooks quando disponível, polling como fallback
└── R2-03d. Event-sourcing (tudo vira evento num broker — Kafka, Redis Streams)

R2-04. Sandbox do agente (quando há LLM + bash tools)
│
├── R2-04a. bwrap (como hoje, Linux only)
├── R2-04b. Docker por tarefa
├── R2-04c. Sem sandbox (trust, containers gerenciados pelo deploy)
└── R2-04d. Configurável por company (cada uma escolhe)

R2-05. Política de custo do LLM
│
├── R2-05a. Hard caps: max_usd + max_usd_per_day + max_new_per_day
│            (como hoje)
├── R2-05b. Soft caps + alerta (não bloqueia, apenas notifica)
├── R2-05c. Rate-limit por company (tokens/minuto)
└── R2-05d. Offload para API própria (proxy com cache/shared budget)

R2-06. Identidade de commit/autor por company
│
├── R2-06a. Git identity por company (como hoje: git_user_name/email no YAML)
├── R2-06b. Identidade única para todas
└── R2-06c. Machine user por company (um usuário por tenant no GitHub/Jira)

R2-07. Credencial: como o operador fornece?
│
├── R2-07a. Env file / secrets.env (como hoje)
├── R2-07b. Vault / AWS Secrets Manager / SSM
├── R2-07c. Interactive login (briar auth login — como hoje)
├── R2-07d. OIDC / SSO automático (onde o provider suportar)
└── R2-07e. Misto (env file para serve, interactive para auth one-off)

R2-08. Notificação de falhas e resultados
│
├── R2-08a. Sinks configuráveis (Slack, Telegram, Email, PagerDuty)
├── R2-08b. Apenas log + arquivo de status
├── R2-08c. Webhook genérico (HTTP POST para URL configurada)
└── R2-08d. Nenhuma (o operador monitora os logs)

R2-09. Testes: cobertura e estratégia
│
├── R2-09a. Manter cobertura atual (~824 testes, property tests, mutation)
├── R2-09b. Reduzir: unit tests + integração, sem property/mutation
├── R2-09c. Mínimo: integração only, contrato via CI
└── R2-09d. TDD-first: escrever os testes antes do código, cobertura como meta

R2-10. Extensibilidade para o usuário final
│
├── R2-10a. Plugin system (registries como hoje — Strategy pattern)
├── R2-10b. Config-driven (YAML/TOML com templates)
├── R2-10c. Ambas (plugins para código, config para comportamento)
└── R2-10d. Nenhuma (fechado, o time mantém as extensions)
```

---

## Rodada 3 — Resto das decisões (10 perguntas)

Estas não bloqueiam a R2, mas fecham o design.

```
R3-01. Interface de entrada
│
├── R3-01a. CLI puro (como hoje — argparse/Click/Clypi)
├── R3-01b. REST API (FastAPI/Starlette) + CLI opcional
├── R3-01c. MCP server (para Claude Code / outros agentes)
├── R3-01d. Webhook receiver (GitHub/GitLab/Slack)
└── R3-01e. Todos os acima (cada um usa o mesmo core)

R3-02. Observabilidade
│
├── R3-02a. Structured logs (JSON) + Sentry
├── R3-02b. Structured logs + métricas (Prometheus / OpenTelemetry)
├── R3-02c. Structured logs + dashboard HTML (como hoje)
└── R3-02d. Mínimo: logs text + status file, sem telemetria externa

R3-03. Pipeline CI/CD
│
├── R3-03a. GitHub Actions (como hoje)
├── R3-03b. GitLab CI
├── R3-03c. Sem CI integrado (o usuário provisiona)
└── R3-03d. CI + deploy automático (push-to-deploy)

R3-04. Empacotamento e distribuição
│
├── R3-04a. pip install (wheel no PyPI)
├── R3-04b. Docker image (multi-stage, mínimo)
├── R3-04c. Binário standalone (Shiv / PyInstaller)
└── R3-04d. Helm chart / Terraform module (deploy como infra)

R3-05. Dependência do Anthropic SDK
│
├── R3-05a. Anthropic SDK como dependência direta (como hoje)
├── R3-05b. Abstração própria — implementa Anthropic, plugável para outros
├── R3-05c. Cliente HTTP puro (sem SDK, só REST calls)
└── R3-05d. Suporta Anthropic + OpenAI + Gemini via interface unificada

R3-06. Browser/session cookies (Jira session auth, etc.)
│
├── R3-06a. Manter suporte (como hoje, requer brave-sync/manual)
├── R3-06b. Apenas API tokens (mais simples, menos flexível)
└── R3-06c. OAuth onde possível, PAT como fallback

R3-07. Modelo de isolamento entre companies
│
├── R3-07a. Processo único, dados separados por company key
├── R3-07b. Processo por company (um scheduler por tenant)
├── R3-07c. Worker pool compartilhado, tasks isoladas
└── R3-07d. Não importa (single-tenant, uma config por instância)

R3-08. Journal / decisão log
│
├── R3-08a. Manter journal (decisões do agent, auditoria)
├── R3-08b. Apenas logs estruturados (sem journal separado)
└── R3-08c. Externalizar para tool do usuário (webhook, syslog)

R3-09. Roadmap pós-v1
│
├── R3-09a. Fechar v1 primeiro, sem plano para v2
├── R3-09b. v1 como MVP, v2 planejada em paralelo
├── R3-09c. Feature flags — cada feature pode ser ligada/desligada
└── R3-09d. Plugin marketplace (terceiros escrevem extractors)

R3-10. Licença e abertura
│
├── R3-10a. Open source (mesma licença do briar atual)
├── R3-10b. Source-available (código visível, uso restrito)
├── R3-10c. Proprietary (closed)
└── R3-10d. Dual license (open para não-comercial, comercial pago)
```

---

## Matriz de dependências

Decisões da R2 que dependem de escolhas específicas da R1:

| R2 | Depende de R1 |
|---|---|
| R2-01 (deploy stack) | R1-04 (execution model) |
| R2-02 (persistência) | R1-05 (multi-tenant config) |
| R2-03 (event delivery) | R1-03 (event sources) + R1-04 |
| R2-04 (sandbox) | R1-07 (LLM dependency) + R1-04 |
| R2-05 (custo LLM) | R1-07 (LLM dependency) + R1-06b (autonomia) |
| R2-06 (identidade) | R1-02b (agent loop) + R1-06 (next steps) |
| R2-07 (credenciais) | R1-01 (extract scope) + R1-05 (config) |
| R2-08 (notificação) | R1-06 (trigger next steps) + R1-04 |
| R2-09 (testes) | R1-08 (scope of reuse) |
| R2-10 (extensibilidade) | R1-01 + R1-03 (scope de features) |

Decisões da R3 que dependem de escolhas específicas:

| R3 | Depende de |
|---|---|
| R3-01 (interface) | R1-04 (execution model) |
| R3-02 (observabilidade) | R1-04 + R1-03 |
| R3-03 (CI/CD) | R2-01 (deploy stack) |
| R3-04 (empacotamento) | R1-04 + R3-01 (interface) |
| R3-05 (SDK) | R1-07 (LLM dependency) |
| R3-06 (auth) | R1-01 (extract scope) |
| R3-07 (isolamento) | R1-05 (multi-tenant config) |
| R3-08 (journal) | R1-02 (serve scope) |
| R3-09 (roadmap) | Todas |
| R3-10 (licença) | Nenhuma (pode ser decidida já) |

---

## Decisões que eu posso consultar (não perguntar)

Estas eu respondo lendo o códigobase atual — não gastam tempo da sua entrevista:

| Tema | O que eu já sei | Onde está |
|---|---|---|
| Tamanho do código | ~824 testes, 25+ registries, Strategy+Registry em toda parte | `tests/`, `ARCHITECTURE.md` |
| Extratores disponíveis | 23 scheduled + 3 JIT | `src/briar/extract/__init__.py` |
| Providers existentes | GitHub, Bitbucket (repo); Jira, Linear, GH Issues, BB Issues (tracker); AWS, GCP, Azure (cloud); Fireflies (meeting) | `extract/_providers/`, `_trackers/`, `_clouds/`, `_meetings/` |
| Actions do agent | `prfix` (comentar PR, fixar CI, resolver conflito) + `implement` (criar branch, PR, implementar) | `commands/agent.py`, `agent/archetypes/` |
| Actions de trigger atuais | jira-comment, jira-transition, github-pr-comment, bitbucket-pr-comment, slack-channel, telegram-chat | `messaging/`, `WRITERS` registry |
| Deploy atual | systemd + launchd, dashboard HTML, `briar runbook serve` como daemon | `DEPLOY_EC2.md`, `IMPLEMENTATION_PLAN.md §9` |
| Testes | pytest + unittest, hypothesis property tests, mutation testing, 824 testes em ~10s | `ARCHITECTURE.md` §Testing |
| Custo medido | Tickets: US$ 0.17–1.03, 35s–9min; Review round: US$ 0.07–0.55 | `docs/decisions/2026-11-18-briar-production-ready.md` §Medidas |
| Sandbox atual | bwrap no Linux, nenhum no macOS | `agent/runner.py` |
| Stack atual | Python 3.10+, pip, pytest, ruff, hatch, GitHub Actions, Postgres opcional | `pyproject.toml`, `.github/workflows/` |
| Config atual | YAML por company, secrets.env, `.briar.toml` por projeto, env vars per-company | `IMPLEMENTATION_PLAN.md`, `FEATURES.md` §10 |

---

## Decisões que VOCÊ precisa responder (perguntar na entrevista)

São decisões de **produto e arquitetura** — o código existe, mas a direção depende do que você quer construir:

```
TODAS as decisões marcadas (perguntar) acima.

Resumo: 27 decisões no total
- Rodada 1:  7 decisões (bloqueiam tudo)
- Rodada 2: 10 decisões (dependem da R1)
- Rodada 3: 10 decisões (fecham o design)
```

Zero destas eu posso responder sozinho — cada uma é uma escolha de produto que muda o que o briar-2 é.

---

## Decisões derivadas (sem perguntar — eu calculo depois das suas respostas)

Depois que você responde as 27, eu derivo automaticamente:

- Quais arquivos do briar atual são reutilizáveis
- Quais precisam ser reescritos
- Qual o esforço estimado por módulo
- Quais providers/extractors entram no v1 (a partir de R1-01)
- Qual a arquitetura final (a partir de R1-02 + R1-04)
- Qual o deploy (a partir de R2-01)

---

## Formato da entrevista

Max 4 perguntas por rodada. Ordem sugerida:

**Rodada 1** (4 perguntas, 3 ficam para a próxima):
1. R1-07 (LLM obrigatório?) — bloqueia arquitetura do agent
2. R1-02 (o que é "serve"?) — bloqueia scope do core
3. R1-04 (modelo de execução) — bloqueia deploy + infra
4. R1-03 (quais eventos) — bloqueia providers e conectores

**Rodada 2** (4 perguntas):
5. R1-01 (extract scope) + R1-05 (multi-tenant config) + R1-06 (next steps) + R1-08 (reuse)

**Rodada 3** (4 perguntas):
6. R2-01 (deploy) + R2-02 (persistência) + R2-05 (custo) + R2-10 (extensibilidade)

**Rodada 4** (resto):
7. R2-03 a R2-09 + R3-01 a R3-10
