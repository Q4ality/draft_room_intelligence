# Codex Routing

This project keeps persistent Codex behavior split across three surfaces:

- `AGENTS.md` for repo rules, commands, validation policy, and skill routing.
- `skills/` for authored reusable project workflows.
- `.agents/skills/` for Codex's standard repo-skill discovery path, using symlinks to `skills/`.
- `.codex/` for project-scoped model, subagent, and custom-agent defaults.

## Defaults

`.codex/config.toml` sets:

- main model: `gpt-5.6`
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

## Operating Rules

- Do not use multiple write agents in parallel.
- Prefer `project-context` before editing unfamiliar areas.
- Prefer `validate-change` before commit or sync.
- Prefer `debug-ingestion` for source coverage, parser, merge, duplicate-row, goalie-stat, and evidence-display issues.
- Escalate to `reviewer` only for meaningful risk; small docs or typo changes do not need it.

## Sources

This configuration follows the Codex manual guidance fetched on 2026-07-16:

- project config files can live at `.codex/config.toml` in trusted repos,
- custom agents can live under `.codex/agents/`,
- custom agent files must define `name`, `description`, and `developer_instructions`,
- `[agents]` supports `max_threads` and `max_depth`,
- repo guidance belongs in `AGENTS.md`.
