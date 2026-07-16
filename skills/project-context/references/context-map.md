# Context Map

Use this map to choose the smallest useful context for common draft-room-intelligence tasks.

## Demo UX, Export, And Readiness

Start with:

- `docs/demo_2025_readiness.md`
- `docs/demo_2025_business_review.md`
- `docs/demo_2025_presenter_script.md`
- `src/draft_room_intelligence/reports/demo_export.py`
- `src/draft_room_intelligence/reports/demo_site.py`
- `src/draft_room_intelligence/reports/demo_acceptance.py`

Validation:

- `make demo-2025-readiness`
- `PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-acceptance outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance`
- `tests/test_demo_acceptance.py`

## Data Ingestion And Source Coverage

Start with:

- `docs/technical_debt_and_ingestion_plan.md`
- `docs/demo_2025_data_contract.md`
- `docs/open_stats_csv_bridge.md`
- `data/reference/ingestion_source_families.csv`
- `src/draft_room_intelligence/data/`
- `src/draft_room_intelligence/reports/ingestion_plan.py`
- `skills/prepare-draft-demo-data/SKILL.md`

Validation:

- `PYTHONPATH=src python3 -m draft_room_intelligence.cli report-ingestion-plan data/reference/ingestion_source_families.csv outputs/ingestion_plan`
- `tests/test_ingestion_plan.py`
- source-specific parser tests under `tests/`

## Modeling, Ranking, And Calibration

Start with:

- `docs/historical_validation.md`
- `docs/demo_2025_modeling_sanity.md`
- `src/draft_room_intelligence/modeling/`
- `src/draft_room_intelligence/evaluation/`
- `src/draft_room_intelligence/optimization/board.py`
- `src/draft_room_intelligence/reports/demo_modeling.py`
- `src/draft_room_intelligence/reports/demo_sanity.py`

Validation:

- `make validate-pilot-2019`
- `PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-modeling outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/modeling_sanity --top-n 40`
- role/modeling tests under `tests/`

## Team-Fit And Roster Analytics

Start with:

- `src/draft_room_intelligence/optimization/team_fit.py`
- `src/draft_room_intelligence/reports/team_depth.py`
- `src/draft_room_intelligence/reports/team_system_audit.py`
- roster import helpers under `src/draft_room_intelligence/data/`
- current team-depth outputs under `outputs/org_team_depth_pre_2025_26_proxy_with_ahl/`

Validation:

- `make team-depth-sample`
- `make nhl-roster-sample`
- team-fit/team-depth tests under `tests/`

## Docs, Workflow, And Project Instructions

Start with:

- `AGENTS.md`
- `README.md`
- `docs/technical_debt_and_ingestion_plan.md`
- `docs/demo_2025_readiness.md`
- repo-local skills under `skills/`

Validation:

- `git diff --check`
- `python3 -m compileall src/draft_room_intelligence`
- targeted skill validation for changed skills.
