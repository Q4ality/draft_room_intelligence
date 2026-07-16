# Repository Guide

## Project Shape

- `src/draft_room_intelligence/data/` - ETL, source parsing, merge, and normalized table loading.
- `src/draft_room_intelligence/modeling/` - reusable feature tables and role-specific models.
- `src/draft_room_intelligence/optimization/` - draft-board scoring and team-fit logic.
- `src/draft_room_intelligence/reports/` - demo exports, readiness reports, audits, and player/report artifacts.
- `tests/` - parser, ETL, report, and scoring coverage.
- `docs/` - project brief, demo readiness, ingestion plan, data contracts, and validation notes.
- `skills/prepare-draft-demo-data/` - workflow skill for single draft-class data staging, ETL, and demo builds.
- `skills/project-context/` - bounded discovery skill for locating relevant docs, code, reports, tests, and commands.
- `skills/validate-change/` - focused validation skill for choosing checks before commit or sync.
- `skills/debug-ingestion/` - troubleshooting skill for source-family ingestion and evidence gaps.
- `.agents/skills/` - symlink discovery layer for repo skills authored under `skills/`.
- `.codex/config.toml` - project-scoped Codex defaults and custom-agent routing.
- `.codex/agents/` - project custom agents for bounded discovery and high-assurance review.
- `data/reference/ingestion_source_families.csv` - source-family manifest for cache-first ingestion planning.

## Key Commands

- Install dev dependencies: `make install-dev`
- Run tests: `make test`
- Run lint: `make lint`
- Run lint plus tests: `make check`
- Build the 2025 demo package: `make demo-2025-readiness`
- Audit ingestion plan: `PYTHONPATH=src python3 -m draft_room_intelligence.cli report-ingestion-plan data/reference/ingestion_source_families.csv outputs/ingestion_plan`
- Run demo acceptance gate: `PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-acceptance outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance`
- Build Codex usage dashboard: `PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-usage outputs/codex_usage/run_log.csv outputs/codex_usage_report`
- Audit Codex routing setup: `PYTHONPATH=src python3 -m draft_room_intelligence.cli audit-codex-routing outputs/codex_routing_audit`

## Working Rules

- Keep raw inputs under ignored `data/raw/` paths and generated artifacts under ignored `outputs/` unless the user explicitly asks to track them.
- Do not commit `.env`, `.env.*`, private credentials, or local IDE folders.
- Preserve user-local changes in the original repo at `/Users/Sergei_Smirnov1/Projects/draft-room-intelligence`; sync only intentional project files.
- Prefer `rg`/`rg --files` for discovery.
- Use `apply_patch` for manual edits.
- Keep new data ingestion cache-first: collect raw files, parse to normalized source tables, merge with audit, then rebuild demo reports.
- Do not add one-off enrichment packs unless `data/reference/ingestion_source_families.csv` and the ingestion audit explain the source-family path.
- Use `debug-ingestion` for source coverage, parser, merge, duplicate-row, goalie-stat, or player-evidence problems.

## Relevant Docs

- Current demo state: `docs/demo_2025_readiness.md`
- Business demo review: `docs/demo_2025_business_review.md`
- Demo presenter flow: `docs/demo_2025_presenter_script.md`
- Data contract: `docs/demo_2025_data_contract.md`
- Systematic ingestion plan: `docs/technical_debt_and_ingestion_plan.md`
- Historical validation: `docs/historical_validation.md`
- Codex routing: `docs/codex_routing.md`
- Codex usage measurement: `docs/codex_usage_measurement.md`

## Validation Policy

- For code changes, run `python3 -m compileall src/draft_room_intelligence` and targeted tests when available.
- For demo/data changes, rebuild or rerun the relevant report plus `report-demo-acceptance`.
- For ingestion changes, rerun `report-ingestion-plan` and document any source-family status movement.
- Use `validate-change` when the right check set is not obvious.
- For routing/config/skill changes, run `audit-codex-routing`.
- Always run `git diff --check` before committing.
- If `pytest` is unavailable in the active Python, state that explicitly instead of treating it as a code failure.

## Model And Agent Routing

- Small deterministic edits affecting one or two files: use the main implementation flow only.
- Unfamiliar code, docs, or data contracts: first use `project-context` to gather bounded context before editing.
- For read-only unfamiliar-area discovery, use the `kb_explorer` custom agent when subagent delegation is useful.
- For high-risk ingestion, ranking, team-fit, security, or data-contract changes, use the `reviewer` custom agent after implementation.
- Repetitive extraction, classification, and simple report generation are good candidates for cheaper/read-only exploration.
- Architecture, ranking calibration, data contracts, security, or changes across many files deserve a higher-assurance review before completion.
- Avoid parallel write agents. Use subagents only for read-heavy exploration or independent validation, and keep their summaries short.

## Definition Of Done

- The requested behavior or plan is implemented in the smallest reasonable scope.
- The relevant docs, reports, or runbooks are updated when behavior or workflow changes.
- Targeted validation was run, or any unavailable check is called out.
- Git status is understood before final handoff.
