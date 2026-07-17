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

`data/reference/codex_task_routing.csv` maps common task classes to the context route, agent path, GPT-5.6 model, reasoning effort, risk level, validation command, and benchmark task id. This is the current decision table for model/agent routing:

- use `gpt-5.6-luna` for clear, repeatable, low-risk edits and usage reports,
- use `gpt-5.6-terra` for read-heavy exploration and everyday demo updates,
- use `gpt-5.6-sol` for high-risk ingestion, ranking, team-fit, and reviewer paths,
- keep low-risk deterministic edits in the main flow,
- use `kb_explorer` for read-only unfamiliar-area discovery when the context route is insufficient,
- use `reviewer` after high-risk ingestion, ranking, or team-fit changes,
- record the matching `measurement_task_id` when benchmarking routed-vs-baseline usage.

## GPT-5.6 Model Mapping

The precise Codex model mapping is:

| Tier | Model slug | Use in this repo |
| --- | --- | --- |
| Sol | `gpt-5.6-sol` | Default project model, reviewer agent, high-risk reasoning, ranking calibration, ingestion, and team-fit changes. |
| Terra | `gpt-5.6-terra` | Read-heavy exploration, bounded context discovery, and normal demo updates. |
| Luna | `gpt-5.6-luna` | Small deterministic edits, structured reporting, usage measurement, and other clear repeatable tasks. |

Codex manual source checked on 2026-07-17: Sol is the complex/open-ended model, Terra is the pragmatic all-rounder, and Luna is for clear repeatable tasks.

Audit the task routing table with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-task-routing \
  data/reference/codex_task_routing.csv \
  data/reference/codex_context_routes.csv \
  outputs/codex_task_routing
```

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
