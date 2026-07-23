# Codex Routing

This project keeps persistent Codex behavior split across three surfaces:

- `AGENTS.md` for repo rules, commands, validation policy, and skill routing.
- `skills/` for authored reusable project workflows.
- `.agents/skills/` for Codex's standard repo-skill discovery path, using symlinks to `skills/`.
- `.codex/` for project-scoped model, subagent, and custom-agent defaults.

## Defaults

`.codex/config.toml` sets:

- main model: `gpt-5.6-sol`
- default reasoning: `medium`
- plan-mode reasoning: `high`
- response verbosity: `low`
- tool output token limit: `6000`
- subagent cap: `max_threads = 3`, `max_depth = 1`

The config intentionally avoids provider, auth, profile, notification, and telemetry settings. Keep those in user config.

## Custom Agents

Use `kb_explorer` for read-only discovery before unfamiliar work:

- unfamiliar code or data contracts,
- demo/report state checks,
- source-family status,
- locating tests and validation commands.

Use `reviewer` after higher-risk implementation:

- ingestion or data-contract changes,
- ranking/scoring/team-fit changes,
- demo credibility changes,
- security or credential-sensitive work,
- broad multi-file changes.

## Skill Discovery

Repo skills are authored under `skills/` for readability and historical continuity. Codex discovers repo skills from `.agents/skills/`, so this project keeps symlinks there for:

- `prepare-draft-demo-data`
- `project-context`
- `validate-change`
- `debug-ingestion`

## Context Routes

`data/reference/codex_context_routes.csv` defines bounded context packs for common task types. Each route lists the minimum docs, source paths, and validation command to inspect before implementation.

Audit the route map with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-context-routes \
  data/reference/codex_context_routes.csv \
  outputs/codex_context_routes
```

## Task Routing

`data/reference/codex_task_routing.csv` maps common task classes to the context route, review model, reasoning effort, risk level, validation command, and benchmark task id. The dispatcher then applies a task phase so a high-risk classification does not force every part of the task onto Sol:

- use `gpt-5.6-luna` for clear, repeatable, low-risk edits and usage reports,
- use `gpt-5.6-terra` for discovery and medium/high-risk implementation,
- use `gpt-5.6-luna` for deterministic validation,
- use `gpt-5.6-sol` for the review phase of high-risk ingestion, ranking, and team-fit work,
- keep low-risk deterministic edits in the main flow,
- use `kb_explorer` for read-only unfamiliar-area discovery when the context route is insufficient,
- use `reviewer` after high-risk ingestion, ranking, or team-fit changes,
- record the matching `measurement_task_id` when benchmarking routed-vs-baseline usage.

## GPT-5.6 Model Mapping

The precise Codex model mapping is:

| Tier | Model slug | Use in this repo |
| --- | --- | --- |
| Sol | `gpt-5.6-sol` | Default interactive model and final reviewer for high-risk ranking, ingestion, and team-fit changes. |
| Terra | `gpt-5.6-terra` | Read-heavy discovery and normal implementation, including bounded high-risk implementation before review. |
| Luna | `gpt-5.6-luna` | Small deterministic edits, validation, structured reporting, and usage measurement. |

Codex manual source checked on 2026-07-17: Sol is the complex/open-ended model, Terra is the pragmatic all-rounder, and Luna is for clear repeatable tasks.

Audit the task routing table with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-task-routing \
  data/reference/codex_task_routing.csv \
  data/reference/codex_context_routes.csv \
  outputs/codex_task_routing
```

### Executable Routing

The routing manifest is enforced for new non-interactive tasks through two commands:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli route-codex-task \
  "Update the demo player detail view" \
  --format shell

PYTHONPATH=src python3 -m draft_room_intelligence.cli run-codex-task \
  "Fix parser source coverage" \
  --task-id ingestion-change \
  --phase implementation

PYTHONPATH=src python3 -m draft_room_intelligence.cli run-codex-task \
  "Review parser source coverage changes" \
  --task-id ingestion-change \
  --phase review
```

`route-codex-task` classifies the task from manifest trigger words and prints the exact command. Use `--task-id` when a task is ambiguous or when deterministic benchmark pairing matters.

`run-codex-task` defaults to `--phase implementation`. Phase routing is:

| Phase | Effective route |
| --- | --- |
| `discovery` | Terra/low with `kb_explorer` guidance |
| `implementation` | Luna for low-risk/repeatable routes; otherwise Terra/medium |
| `validation` | Luna/low |
| `review` | The manifest's original model, reasoning, and agent; high-risk routes use Sol/high reviewer |
| `full` | Legacy whole-task behavior using the manifest route |

The command passes the effective `--model` and `model_reasoning_effort` directly to `codex exec --json`. It records the phase plus exact uncached input, cached input, and output tokens in `outputs/codex_usage/run_log.csv`. A failed launch is also recorded so routing reliability remains visible.

The project-level default remains Sol for interactive tasks. Automatic tier selection applies when the task is launched through `run-codex-task`; changing a routing CSV cannot mutate a task that is already running.

### Telemetry

Historical model selection can be inspected from the local Codex state database:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-telemetry \
  outputs/codex_telemetry \
  --project-root .
```

This report counts tasks by model and identifies child/subagent tasks. The state database's `tokens_used` value is a cumulative internal counter, so it is retained only for diagnostics and never summed as spend. Use `run-codex-task` for exact future run measurements, then compare matched baseline and routed tasks with `report-codex-usage`.

## Operating Rules

- Do not use multiple write agents in parallel.
- Prefer `project-context` before editing unfamiliar areas.
- Prefer `validate-change` before commit or sync.
- Prefer `debug-ingestion` for source coverage, parser, merge, duplicate-row, goalie-stat, and evidence-display issues.
- Escalate to `reviewer` only for meaningful risk; small docs or typo changes do not need it.
- Measure routing impact with the benchmark loop in `docs/codex_usage_measurement.md`.

## Health Check

Run this after changing `.codex/`, `.agents/skills/`, repo skills, or routing docs:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli audit-codex-routing \
  outputs/codex_routing_audit
```

## Sources

This configuration follows the Codex manual guidance fetched on 2026-07-16:

- project config files can live at `.codex/config.toml` in trusted repos,
- custom agents can live under `.codex/agents/`,
- custom agent files must define `name`, `description`, and `developer_instructions`,
- `[agents]` supports `max_threads` and `max_depth`,
- repo guidance belongs in `AGENTS.md`.
