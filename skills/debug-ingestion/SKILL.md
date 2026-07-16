---
name: debug-ingestion
description: Diagnose and improve draft-room-intelligence data ingestion problems. Use when source coverage, cached raw files, parser output, identity matching, duplicate stat rows, goalie metrics, playoff/adult exposure, evidence-depth movement, or demo player histories look wrong or incomplete.
---

# Debug Ingestion

Use this skill to move ingestion work through the repeatable collect -> parse -> merge -> audit loop. The goal is to fix source-family pipelines, not add disconnected one-off rows.

## Workflow

1. Identify the affected source family in `data/reference/ingestion_source_families.csv`.
2. Run or inspect the ingestion plan audit.
3. Locate the raw cache, normalized source output, merge output, and demo evidence for the affected players.
4. Classify the failure:
   - missing raw cache,
   - parser did not extract rows,
   - identity match failed,
   - merge/dedup collapsed or duplicated rows incorrectly,
   - role-specific fields are wrong,
   - demo export does not display available evidence.
5. Fix the earliest failing stage.
6. Rerun the source-family audit and the relevant demo acceptance/sanity report.

## Core Commands

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-ingestion-plan \
  data/reference/ingestion_source_families.csv \
  outputs/ingestion_plan

PYTHONPATH=src python3 -m draft_room_intelligence.cli audit-prospect-stats \
  outputs/prospect_stats_audit \
  <dataset-or-source-dir>

PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-acceptance \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance
```

## Guardrails

- Keep raw source files under ignored `data/raw/` cache paths.
- Preserve source URLs or source IDs in normalized rows.
- Separate regular season from playoffs when the source provides both.
- Store goalie SV%, GAA, SO, wins, losses, and ties/overtime separately from skater production.
- Do not hide weak coverage; update evidence-depth or gap reports instead.
- Do not add another curated pack unless the source-family manifest explains why it exists and how it will become repeatable.

## References

- Read `references/source-family-debug.md` for source-family-specific checks and common failure modes.
