# Check Matrix

Use the smallest set that covers the changed behavior.

## Docs, AGENTS, Or Skills Only

Run:

```bash
git diff --check
python3 -m compileall skills
```

If a skill changed and the skill validator is available:

```bash
python3 /Users/Sergei_Smirnov1/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-dir>
```

If validation fails because `yaml` is unavailable, say so and inspect `SKILL.md` frontmatter plus `agents/openai.yaml` manually.

## General Python Modules

Run:

```bash
python3 -m compileall src/draft_room_intelligence
git diff --check
```

Then choose targeted tests from `tests/` by filename or `rg` match. If no targeted test exists, run the smallest CLI smoke command that exercises the changed path.

## Demo Export, Site, Or Demo Reports

Run:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-acceptance \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance
```

If export logic changed materially, also run:

```bash
make demo-2025-readiness
```

Targeted tests to consider:

- `tests/test_demo_acceptance.py`
- demo/export/site tests found by `rg -n "demo_|build-demo|demo_acceptance" tests`

## Ingestion, Source Coverage, Or Data Contract

Run:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-ingestion-plan \
  data/reference/ingestion_source_families.csv \
  outputs/ingestion_plan
```

If a parser or merge changed, run matching parser/import/merge tests and a source-specific CLI smoke command when fixtures exist.

Targeted tests to consider:

- `tests/test_ingestion_plan.py`
- parser tests found by `rg -n "import|parse|merge|source|stat" tests`

## Modeling, Ranking, Calibration, Or Team Fit

Run at least one report-level sanity check:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-modeling \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/modeling_sanity \
  --top-n 40

PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-sanity \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_sanity
```

If ranking changes can affect business-demo credibility, also run demo acceptance.

For team-fit changes, prefer:

```bash
make team-depth-sample
```

or, if roster import changed:

```bash
make nhl-roster-sample
```

## Commit And Sync

Before committing:

```bash
git status --short
git diff --check
```

When syncing to `/Users/Sergei_Smirnov1/Projects/draft-room-intelligence`, stage only intended files. Leave local `.env`, `.env.*`, `.env.example` changes, and `.idea/` untouched unless the user explicitly asks.
