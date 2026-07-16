---
name: project-context
description: Find the minimum relevant draft-room-intelligence files, docs, reports, tests, commands, and source-family context before editing unfamiliar code, data ingestion, demo exports, modeling, team-fit analytics, or project documentation. Use when a task spans unknown modules, data contracts, generated demo artifacts, or needs bounded repo discovery before implementation.
---

# Project Context

Use this skill to gather a compact, task-specific context pack before changing unfamiliar parts of the repository. The goal is to avoid loading broad docs, large outputs, or unrelated source files.

## Workflow

1. Classify the task area:
   - demo UX/export/readiness,
   - data ingestion/source coverage,
   - modeling/scoring/calibration,
   - team-fit and roster analytics,
   - docs/process/repo workflow,
   - tests/validation.
2. Read only the relevant section of `references/context-map.md`.
3. Prefer the matching route in `data/reference/codex_context_routes.csv` when it covers the task.
4. Use `rg` or `rg --files` to find exact files, symbols, tests, and reports.
5. Return a bounded context summary before implementation when the path is not obvious.

## Output Contract

Return no more than:

- 5 relevant source files or symbols,
- 5 relevant docs/reports,
- 5 relevant tests or validation commands,
- 3 open risks, blockers, or missing facts,
- 1 recommended next implementation path.

Do not dump full files, generated JSON, or large CSV/report outputs. Cite paths and summarize why each item matters.

## Commands To Prefer

```bash
rg --files
rg -n "pattern" path/
PYTHONPATH=src python3 -m draft_room_intelligence.cli --help
git status --short
git diff --check
```

For demo/data tasks, prefer existing reports over ad hoc inspection:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-ingestion-plan \
  data/reference/ingestion_source_families.csv \
  outputs/ingestion_plan

PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-acceptance \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance
```

## References

- Read `references/context-map.md` for task-area routing and canonical files.
- Use `data/reference/codex_context_routes.csv` as the machine-readable route list for repeatable benchmarkable context packs.
