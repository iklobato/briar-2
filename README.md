# briar-2

Slim, multi-company, event-driven CLI. One process per company polls
Slack, GitLab, GitHub and Jira, queues what it finds, and asks Claude what
to do with each event.

**It never sends anything.** Every action is a draft a human reviews and
sends (decision D17). The whole point is to prepare the reply, not to
publish it.

## The loop

```
poll sources -> dedup -> priority queue -> agent (Claude) -> draft -> record
```

- **Poll**: every source has its own interval (`poll_every`).
- **Dedup**: an event seen in the last 5 minutes is dropped.
- **Queue**: one JSON file per event, ordered by priority then time.
- **Agent**: one isolated agent per event, up to `cap` at a time. The agent
  reads the event plus the correlated knowledge of the company and picks one
  action.
- **Lock**: an action holds a lock on its resource (`mr/gitlab/123`) while it
  runs, so two events never touch the same merge request at once.
- **Record**: the outcome and the draft land in the knowledge store.

## Install

```bash
cd ~/briar-2
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Run

```bash
briar2 serve gatik                     # one company
briar2 serve --all                     # every company in the config dir
briar2 serve gatik --config-dir /etc/briar-2/companies
```

The config dir holds one directory per company, each with a `config.yaml`:

```
companies/
  gatik/
    config.yaml
  acme/
    config.yaml
```

## Config

```yaml
company: gatik          # name, used in paths and log lines
cap: 4                  # max parallel agents (default: number of CPUs)

sources:
  slack:
    bot_token_env: SLACK_BOT_TOKEN
    channels: [C0B6LCLAJ82]
    poll_every: 30s
  gitlab:
    token_env: GITLAB_TOKEN
    project: gatik/ai-infra
    url: https://gitlab.com     # self-hosted instance URL also works
    poll_every: 1m
  github:
    token_env: GITHUB_TOKEN
    repos: [acme/tool]
    url: https://api.github.com  # Enterprise: https://host/api/v3
    poll_every: 2m
  jira:
    token_env: JIRA_TOKEN
    jql: project = GAIT
    url: https://gatik-engineering.atlassian.net
    poll_every: 5m

actions:
  slack_draft: true      # the agent may draft a Slack reply
  gitlab_approve: false  # approve merge requests
  ci_fix_attempts: 3     # CI fix attempts per merge request

llm:
  model: claude-opus-5-5
  effort: medium
  api_key_env: ANTHROPIC_API_KEY

paths:
  knowledge_root: ~/.cache/briar/knowledge/
  lock_root: ~/.cache/briar/locks/
  queue_root: ~/.cache/briar/queue/

stale_after_minutes: 60  # when an event needs a human
```

The config is strict: an unknown key or an unknown source is an error, not a
silent default. Intervals are `30s`, `5m` or `1h`.

Tokens live in environment variables, never in the config file.

## Actions the agent can pick

| Name | What it drafts |
|---|---|
| `record` | nothing to send, the event is recorded only |
| `slack_draft` | a reply for the thread, ready to paste |
| `slack_react` | the marker emoji on the message |
| `gitlab_comment` | a comment for the merge request |
| `gitlab_label` | a label for the merge request |
| `gitlab_approve` | an approval, with the head sha for verification |

## Where the files land

| What | Where |
|---|---|
| Knowledge and drafts | `~/.cache/briar/knowledge/<company>/` |
| Queue | `~/.cache/briar/queue/<company>/` |
| Failed events | `~/.cache/briar/queue/<company>/dead/` |
| Locks | `~/.cache/briar/locks/` |
| Log | `~/.cache/briar/logs/briar2.log` |

Every log line carries the event id, so one event can be followed from the
poll to the draft.

## Deploy (one process per company)

```bash
sudo cp deploy/briar2@.service /etc/systemd/system/
sudo systemctl enable --now briar2@gatik
```

The unit reads its tokens from `/etc/briar-2/gatik.env` and its config from
`/etc/briar-2/companies/gatik/config.yaml`.

## Shadow run

Before a company goes live, run it for 7 days with every output as a draft.
Read the drafts, measure how many were worth sending, then decide. The
run leaves no trace outside the knowledge store, so it is safe to run
against production systems.

## Tests

```bash
python3 -m pytest
```
