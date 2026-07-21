# Historical Draft-Class ETL

## Purpose

The historical ETL creates one normalized dataset per NHL draft class from 2014 through 2026. It separates network collection from deterministic parsing and enrichment:

1. Cache official NHL draft-pick JSON under `data/raw/nhl_draft/<year>/picks.json`.
2. Generate normalized base tables under `data/processed/draft_classes/<year>/base`.
3. Apply configured source enrichment when a local export exists.
4. Publish the reusable snapshot under `data/processed/draft_classes/<year>/final`.
5. Write class-level status and integrity results under `outputs/draft_range_etl`.

The tracked class configuration is `data/reference/draft_class_etl.csv`. Relative paths are resolved from the project root, so a class can use standard cache paths or override them with an existing normalized dataset.

## Commands

Collect or reuse official raw draft lists:

```bash
PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli collect-nhl-draft-range \
  data/raw/nhl_draft --start-year 2014 --end-year 2026
```

Inspect readiness without changing processed datasets:

```bash
PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli etl-draft-range \
  data/reference/draft_class_etl.csv outputs/draft_range_etl \
  --project-root . --start-year 2014 --end-year 2026 --dry-run
```

Build every ready class:

```bash
PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli etl-draft-range \
  data/reference/draft_class_etl.csv outputs/draft_range_etl \
  --project-root . --start-year 2014 --end-year 2026
```

Completed classes are skipped only after their normalized integrity checks pass and the stored input fingerprint matches current cached files. Adding or changing an enrichment export automatically schedules that class for rebuild. Use `--force` to rebuild unchanged inputs and `--fail-fast` when a CI job should stop on the first class failure.

## Current Baseline

The first run produced 13 valid class snapshots with 2,840 drafted players:

- 2014-2018 and 2020-2024 use the official NHL draft API cache as their baseline.
- 2019 preserves the existing normalized outcome-validation pilot.
- 2025 preserves the enriched business-demo dataset.
- 2026 uses the now-published official NHL draft list.
- All 13 pass player-ID, selection-ID, draft-year, overall-pick, ranking, outcome, and stat-reference integrity checks.

This is full draft-list coverage, not full scouting-evidence coverage. The NHL draft feed supplies selection, team, position, nationality, size, amateur team, and amateur league fields. It does not supply pre-draft season statistics, birth dates, handedness, consensus rankings, or reliable historical NHL outcomes. Baseline outcome tables therefore remain empty: unknown NHL outcomes must never be represented as observed zero-game careers.

Only 2019 and 2025 currently carry meaningful season-stat rows. A class should not be promoted to a business demo until its source enrichments and evidence-depth audit pass.

## Enrichment Order

Use the same cache-first adapter sequence for each class:

1. Resolve player identity and biographical fields.
2. Add league season histories with regular-season/playoff separation.
3. Add goalie-specific SV%, GAA, record, and shutouts.
4. Add consensus/scouting evidence where permitted.
5. Add NHL outcome labels for mature historical classes.
6. Run duplicate reconciliation, prospect-stat audit, and historical validation.

Prioritize 2014-2020 first for outcome-model validation, then 2021-2024 for recent-class backtesting, and 2026 for the next live demo.

## Integrity Contract

A class is resumable only when:

- all five required normalized tables exist;
- player and draft-selection IDs are unique and equal;
- every selection has the configured draft year and unique overall pick;
- every player has a ranking row;
- outcome rows, when present, reference known players; baseline classes may have zero outcome rows;
- stat rows do not reference unknown players.

The batch report records player counts, stat-line counts, base source, optional enrichment state, and quality status for every class.
