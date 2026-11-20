# Árvore de Decisões — briar-2

Data: 2026-11-19
Contexto: Slim do briar CLI para core de extract + serve multi-empresa com eventos.
Novo projeto em ~/briar-2.

---

## Rodada 1 — Escopo e arquitetura

| # | Decisão | Escolhido | Por quê | Depende de |
|---|---------|-----------|---------|------------|
| D1 | O que é "extract" | **Todos 23+3** (scheduled + JIT) | Cobertura máxima; usuário pode desabilitar extratores individuais no YAML | — |
| D2 | O que é "serve" | **Scheduler + agente LLM + eventos** | Core completo; serve é o diferencial do briar | D1 |
| D3 | Fontes de evento | **Todos os feeds**: GitHub notifications, GitLab todos, Jira JQL, Slack DMs/mentions | Máxima cobertura; primeira slice implementa todos | D2 |
| D4 | Runtime model | **CLI com polling interno** (um só binário; `serve` vira daemon) | CLI para comandas manuais; serve roda polling no mesmo processo | D2, D3 |
| D5 | Multi-tenancy | **Processo por empresa** (systemd por company) | Isolamento total, falha de uma não afeta outras; alinhado com doc de eventos W24 | D4 |
| D6 | Trigger action | **Agente executa ações, híbrido por tipo** | Review/CI → agent age; status change → registra; Slack DM → draft | D2, D3 |
| D7 | Deploy | **VPS dedicado** (systemd por empresa) | Simples, funciona atrás de firewall, sem endpoint público | D4, D5 |
| D8 | LLM provider | **Anthropic apenas** | SDK nativo, custo medido, sem overhead de manter N providers | D2, D6 |

## Rodada 2 — Arquitetura detalhada

| # | Decisão | Escolhido | Por quê | Depende de |
|---|---------|-----------|---------|------------|
| D9 | CLI vs eventos | **CLI resolve polling internamente** | Um só binário, sem processo separado; `briar serve` ativa o loop | D4 |
| D10 | Credenciais | **Env-file + convenção PROVIDER_<COMPANY>_KEY** | Simples para outros usuários; convenção já existe no código atual | D5 |
| D11 | Knowledge store | **File store** (markdown em ~/.cache/briar/knowledge/) | Sem dependência de banco; funciona para escala inicial (1-10 empresas) | D4, D5 |
| D12 | Sandbox agente | **Configurável** (allowlist de commands declarada no runbook YAML) | Flexibilidade por empresa + segurança default | D6 |
| D13 | Custos/limites | **Sem limites internos** (confia no Anthropic SDK max_budget_usd) | Mantém código enxuto; usuário controla via SDK + env var | D8, D6 |
| D14 | Empacotamento | **Sem empacotamento por enquanto** (pip install -e . ou wheel local) | Foco em funcionalidade primeiro | D7 |

## Rodada 3 — Detalhes finais

| # | Decisão | Escolhido | Por quê | Depende de |
|---|---------|-----------|---------|------------|
| D15 | Quality rules | **Manter como opt-in** | Código já existe; usuário ativa por repo no YAML | — |
| D16 | Decision journal | **Remover** | Ferramenta interna; produção unattended não precisa | — |

## Rodada 4 — Cenários do dia a dia (Gatik)

| # | Decisão | Escolhido | Por quê | Depende de |
|---|---------|-----------|---------|------------|
| D17 | Postar ou rascunhar | **Nunca envia** — sempre produz rascunho na thread, Henry envia | Igual alert-triage; Henry aprova antes de sair. Custa pouco, aprova rápido. | D2 |
| D18 | Marcador de já tratado | **Reação emoji** no evento original (✅ / ⛔ / 👀) | Estado mínimo, barato, visível no Slack. Próxima passagem do poll pula se tem reação de Henry. | D2, D3 |
| D19 | Correlação cross-source | **Sempre** cruza todas as fontes antes de agir | Um alerta pode citar ticket, um MR pode ter thread com Jira; contexto é necessário para decisão correta. | D2, D3 |
| D20 | Validação pré-live | **7 dias shadow** (mede acurácia, Henry decide depois) | Custo alto mas risco baixo; barra de 9/9 não atingida na Gatik foi aceita por Henry. Repetir o padrão. | D2, D3 |
| D21 | Escalonamento humano | **3 níveis**: comenta na thread → DM Henry → espera aprovação humana | Comenta no mesmo lugar onde o problema apareceu; DM se não resolve em 5min; parada total em 10min para ações destrutivas. | D2, D6 |
| D22 | CI fix loop | **Até 3 tentativas** por PR (dependência, lint, version bump) | Fixes de CI são idempotentes e baratos; 3 tenta cobrir os casos comuns sem loop infinito. | D6 |
| D23 | Credenciais expiradas | **Track metadata + alerta antecipado** (N dias antes) | Token do Atlassian da Gatik venceu sem aviso; briar-2 avisa antes e opera read-only se já expirou. | D5, D6 |
| D24 | Knowledge sync | **Somente no Mac** (por enquanto) | Henry escolheu; VPS não mantém cópia por enquanto. Deixa para depois quando o fluxo estiver claro. | D5 |

## Rodada 5 — Paralelismo (decisões D25-D36)

| # | Decisão | Escolhido | Por quê | Depende de |
|---|---------|-----------|---------|------------|
| D25 | Eventos mesma empresa | **Paralelo com cap** (N configurável) | Mais rápido que serial; cap evita sobrecarga. | D5, D4 |
| D26 | Agente por evento | **Fork por evento** (um subagente isolado por evento) | Isolamento total; falha de um não afeta outros. Custo: mais tokens. | D6, D25 |
| D27 | Cap global | **Sem limite** (cada empresa gerencia seu próprio cap) | Henry escolheu; confia no LLM provider rate limit como teto natural. | D5, D25 |
| D28 | Dedup eventos | **Janela deslizante** (tipo + id + timestamp arredondado) | Flapping é comum em alertas; evita processar o mesmo evento repetidamente. | D3, D25 |
| D29 | Estado compartilhado | **Lock explícito** por recurso (arquivo/chave) | Evita read-during-write quando dois agentes paralelos mexem no knowledge store. | D11, D26 |
| D30 | Fila cheia | **Fila com espera** (evento espera até slot liberar) | Nada se perde; cap é respeitado. | D25 |
| D31 | Coordenação paralela | **Orquestrador + workers** dentro do mesmo processo | Orquestrador decide prioridade, spawna workers isolados. Workers não se falam diretamente. | D26, D25 |
| D32 | Timeout por agente | **Sem timeout interno** (confia nos timeouts do OS/LLM provider) | Henry escolheu; subprocessos ainda têm timeout do sistema operacional. | D26 |
| D33 | Estrutura da fila | **Fila por empresa** (cada empresa = linha de comando separada) | Cada empresa roda em systemd service separado; fila isolada por processo. | D5, D25 |
| D34 | Prioridade da fila | **Por tipo de ação** (MR review > CI fix > alert triage > status change) | Ações que bloqueiam humanos têm prioridade; destrutivas primeiro. | D25, D30 |
| D35 | Recuperação de crash | **Recomeça do zero** (eventos em execução são perdidos, próximos voltam pelo polling) | Simples; poller naturalmente pega eventos não processados na próxima janela. | D4, D30 |
| D36 | Observabilidade | **Trace ID por evento** (cada evento carrega ID em todas as linhas de log) | Permite rastrear fluxo paralelo completo no log. | D25, D26 |
| D37 | Default cap por empresa | **Número de CPUs** da máquina | Aproveita hardware; Henry pode sobrescrever por empresa no YAML. | D25 |
| D38 | Mecanismo de lock | **flock** em arquivo por recurso | Nativo, simples, funciona em qualquer filesystem. Sem dependência extra. | D29 |
| D39 | Overflow da fila | **Sem limite** (cresce até disco acabar; Henry vê no log e escala) | Henry escolheu; fila grande é menos pior que perder eventos. | D30, D37 |

## Rodada 6 — Conflitos, locks e prioridade (D40-D47)

| # | Decisão | Escolhido | Por quê | Depende de |
|---|---------|-----------|---------|------------|
| D40 | Tipos de conflito cobertos | **Mesmo MR/GitLab, mesma thread Slack, mesmo arquivo knowledge, CI fix + approve** | Todos os cenários reais identificados no dia a dia da Gatik. | D26, D29 |
| D41 | Granularidade do lock | **Por recurso exato** (MR/NNN, thread/TS, arquivo/path) | Máximo paralelismo; lock só bloqueia o recurso em conflito, não tudo. | D29 |
| D42 | Duração do lock | **Só durante a ação** (não cobre validação pós-ação) | Lock é adquirido, ação é executada, lock liberado IMEDIATAMENTE. Validação usa o estado persistido pela ação, não precisa de lock. | D41 |
| D43 | Deadlock avoidance | **Timeout 5s + retry com backoff exponencial** | Simples, evita starvation. Se lock não liberar em 5s, libera e tenta de novo. | D29, D38 |
| D44 | Conflito: mesma thread Slack | **Espera + age depois** (lê estado atual após lock liberar) | Segundo agente espera o primeiro terminar, depois vê o estado real da thread antes de agir. Evita draft conflict. | D41, D42 |
| D45 | Conflito: knowledge store | **Lock por arquivo + espera** (flock no path exato) | Segundo agente espera, lê versão atualizada, escreve. Sem read-during-write. | D29, D41 |
| D46 | Conflito: CI fix + approve | **Lock no MR + head_sha check** | CI fix adquire lock do MR antes de commitar. Approve valida head_sha ANTES de aprovar. Se SHA mudou, re-verifica. | D41, D22 |
| D47 | Prioridade + cooperação | **Fila priorizada + cooperação** (FIFO dentro de cada tipo) | Orquestrador pega por (priority_score, timestamp). Evento alta prioridade pega slot livre; se todos ocupados, espera o atual terminar. Sem preempção. | D34, D31 |
| D48 | Starvation avoidance | **FIFO dentro do tipo** (não penaliza eventos antigos por tipo) | Um alerta esperando 10min não é penalizado se MRs chegarem no meio. Justo por tipo. | D47 |
| D49 | Implementação da fila | **Arquivos JSON + flock** em ~/.cache/briar/queue/<empresa>/ | Persistente, debugável, funciona em qualquer filesystem. Eventos sobrevivem a crash. | D33 |
| D50 | Ordenação da fila | **Tupla (priority_score, timestamp)** — ordena a cada inserção | Prioridade primeiro, FIFO dentro do mesmo score. Simples, previsível. | D47, D49 |
| D51 | Lock em ações externas | **Manual no código** — flock antes de cada API call, libera após | Cobre todos os casos; explícito, sem mágica. O wrapping fica no caller, não num middleware. | D41 |
| D52 | Cross-empresa | **Sem lock cross-empresa** (cada processo é independente) | Processos separados não compartilham locks. Se duas empresas compartilham credencial do GitLab, risco de conflito é do usuário. | D5, D41 |
| D53 | Ação falha com lock | **Libera + dead letter queue** (evento vai para fila de mortos para Henry inspecionar) | Lock não fica retido por erro. Henry vê o que falhou e decide reenfileirar ou abortar. | D42 |
| D54 | Stale detection + lock | **Leitura separada, escrita com lock** (stale detection só lê estado, age com lock) | Stale detection não bloqueia ações. Se detecta stale, adquire lock de escrita e age. | D31, D41 |

## Riscos abertos

- **N+1 empresas no file store**: file store escala bem até ~10 empresas no mesmo disco. Para além disso, Postgres backend é a migração natural.
- **Sem limites de custo hardcoded**: confia no Anthropic SDK. Se o SDK mudar comportamento, briar-2 fica exposto. Mitigar: logging de gasto após cada call.
- **Sandbox configurável**: se o usuário declarar allowlist ampla (todos os commands), perde a proteção. Documentar o risco.
- **Knowledge sync**: operar só no Mac limita deploy em VPS. Quando Henry quiser rodar em VPS, precisa definir o fluxo de sync primeiro.
- **Shadow de 7 dias**: consome tempo e tokens antes de ir live. Para empresas com menos volume de eventos, pode ser encurtado via config.
- **No timeout por agente**: se um agente travar no LLM, consome o cap da empresa até o provider derrubar. Monitorar duração de cada execução.
- **Recomeça do zero no crash**: eventos em andamento são perdidos. Mitigar: checkpoint do poller a cada evento iniciado.
- **Dead letter queue sem auto-reprocessamento**: eventos na DLQ ficam lá até Henry agir. Se Henry estiver ausente, eventos acumulam. Considerar auto-reprocessamento com limite.

## Pendente (não decidido, não bloqueia)

- Observabilidade: logs estruturados + Sentry opcional (herdar do briar atual)
- Testes: reaproveitar infra de testes do briar atual
- Extensibilidade: Strategy + Registry pattern (herdar do briar atual)
- Knowledge sync entre máquinas (aguardando definição de fluxo pelo Henry)
- Default do cap por empresa (configurável via YAML, valor padrão a definir)
- Mecanismo de lock (flock, file lock, sqlite — valor padrão a definir)
- Overflow da fila (limite de tamanho, drop vs alerta)
- Auto-reprocessamento da DLQ (limite de tentativas, intervalo)

## Riscos abertos

- **N+1 empresas no file store**: file store escala bem até ~10 empresas no mesmo disco. Para além disso, Postgres backend é a migração natural.
- **Sem limites de custo hardcoded**: confia no Anthropic SDK. Se o SDK mudar comportamento, briar-2 fica exposto. Mitigar: logging de gasto após cada call.
- **Sandbox configurável**: se o usuário declarar allowlist ampla (todos os commands), perde a proteção. Documentar o risco.
- **Knowledge sync**: operar só no Mac limita deploy em VPS. Quando Henry quiser rodar em VPS, precisa definir o fluxo de sync primeiro.
- **Shadow de 7 dias**: consome tempo e tokens antes de ir live. Para empresas com menos volume de eventos, pode ser encurtado via config.
- **No timeout por agente**: se um agente travar no LLM, consome o cap da empresa até o provider derrubar. Monitorar duração de cada execução.
- **Recomeça do zero no crash**: eventos em andamento são perdidos. Mitigar: checkpoint do poller a cada evento iniciado.

## Pendente (não decidido, não bloqueia)

- Observabilidade: logs estruturados + Sentry opcional (herdar do briar atual)
- Testes: reaproveitar infra de testes do briar atual
- Extensibilidade: Strategy + Registry pattern (herdar do briar atual)
- Knowledge sync entre máquinas (aguardando definição de fluxo pelo Henry)
- Default do cap por empresa (configurável via YAML, valor padrão a definir)
- Mecanismo de lock (flock, file lock, sqlite — valor padrão a definir)
- Overflow da fila (limite de tamanho, drop vs alerta)
