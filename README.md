# Draft-Room Decision Intelligence

Python prototype for an explainable draft and roster decision-intelligence workflow.

The current wedge is NHL draft analysis: build normalized pre-draft datasets, enrich them with external exports, compare baseline approaches, and evaluate simple role-specific models.

## Repository Layout

- `docs/project_brief.md` - source project/development draft.
- `src/draft_room_intelligence/data/` - ETL, import, merge, and normalized table loading.
- `src/draft_room_intelligence/evaluation/` - baseline scoring and reporting utilities.
- `src/draft_room_intelligence/modeling/` - reusable feature table generation and role-specific models.
- `src/draft_room_intelligence/projection/` - projection helpers and production adjustment logic.
- `src/draft_room_intelligence/optimization/` - draft-board and team-fit scoring.
- `src/draft_room_intelligence/reports/` - Markdown player card generation.
- `tests/` - CLI, ETL, merge, and evaluation coverage.
- `data/reference/` - tracked reference tables such as league context.
- `data/processed/` - tracked sample/pilot normalized datasets.
- `data/raw/` - local raw inputs such as HockeyDB HTML and Elite Prospects exports. Ignored by git.
- `outputs/` - local exports from feature tables, model runs, and ad hoc analysis. Ignored by git.
- `skills/prepare-draft-demo-data/` - repo-local Codex skill for staging demo data, auditing readiness, and running the single-class ETL/demo flow.

## Quick Start

```bash
cd /path/to/current_project
python3 -m venv .venv
make install-dev
make demo
make evaluate-consensus
make evaluate-projection
make evaluate-pilot-consensus
make evaluate-pilot-adjusted-production
make evaluate-pilot-hybrid
make test
```

Equivalent commands without `make`:

```bash
python -m pip install -e ".[dev]"
python -m draft_room_intelligence.cli --help
python -m draft_room_intelligence.cli demo
python -m draft_room_intelligence.cli evaluate tests/fixtures/historical_prospects.csv --baseline consensus --precision-n 1
python -m draft_room_intelligence.cli evaluate tests/fixtures/historical_prospects.csv --baseline projection --precision-n 1
python -m draft_room_intelligence.cli evaluate data/processed/pilot_2019 --baseline adjusted-production --precision-n 25
python -m draft_room_intelligence.cli evaluate data/processed/pilot_2019 --baseline hybrid --precision-n 25
python -m draft_room_intelligence.cli export-feature-table data/processed/pilot_2019 outputs/features_2019.csv
python -m draft_room_intelligence.cli evaluate-role-models data/processed/pilot_2019 --feature-output outputs/features_2019.csv --model-output outputs/role_models_2019.csv --precision-n 25
python -m draft_room_intelligence.cli build-demo-readiness data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup/final outputs/demo_2025_openstats_russian_nordic_cleanup
python -m draft_room_intelligence.cli validate-eliteprospects data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli etl-draft-year data/processed/etl_2019 --draft-year 2019 --base-dir data/processed/pilot_2019 --eliteprospects-csv data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli etl-draft-year data/processed/etl_2019 --draft-year 2019 --hockeydb-draft-html data/raw/hockeydb/2019/nhl2019e.html --eliteprospects-csv data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli etl-draft-year data/processed/etl_2019 --draft-year 2019 --hockeydb-draft-html data/raw/hockeydb/2019/nhl2019e.html --hockeydb-player-pages-dir data/raw/hockeydb/2019/player_pages --eliteprospects-csv data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli process-eliteprospects data/raw/eliteprospects_2019.csv data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep --draft-year 2019
python -m draft_room_intelligence.cli import-eliteprospects data/raw/eliteprospects_2019.csv data/processed/eliteprospects_2019 --draft-year 2019
python -m draft_room_intelligence.cli merge-eliteprospects data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep
python -m draft_room_intelligence.cli generate-match-map-template data/processed/pilot_2019 data/processed/pilot_2019_ep/unmatched_source_players.csv data/reference/eliteprospects_2019_match_map_template.csv
python -m draft_room_intelligence.cli merge-eliteprospects data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep --match-map data/reference/eliteprospects_2019_match_map.csv
python -m draft_room_intelligence.cli report-merge-quality data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep
python -m pytest
```

The package exposes the same CLI as `draft-room-intel` after editable install.

## Development Workflow

- `make install-dev` - install the project in editable mode with development tools.
- `make demo` - run the sample projection, scouting, team-fit, and player-card flow.
- `make demo-2025-readiness` - rebuild the current 2025 demo site, data-gap report, and modeling sanity report from the tracked cleanup dataset.
- `make validate-pilot-2019` - compare consensus, production, hybrid, and role-aware scoring approaches against 2019 NHL outcomes.
- `make evaluate-consensus` - evaluate the consensus baseline against the fixture CSV.
- `make evaluate-projection` - evaluate the heuristic projection baseline against the fixture CSV.
- `make evaluate-adjusted-production` - evaluate the adjusted-production baseline against the fixture CSV.
- `make evaluate-pilot-consensus` - evaluate the consensus baseline against the normalized 2019 pilot tables.
- `make evaluate-pilot-projection` - evaluate the heuristic projection baseline against the normalized 2019 pilot tables.
- `make evaluate-pilot-adjusted-production` - evaluate the adjusted-production baseline against the normalized 2019 pilot tables.
- `make evaluate-pilot-hybrid` - evaluate the weighted consensus/projection/adjusted-production hybrid baseline against the normalized 2019 pilot tables.
- `draft-room-intel export-feature-table <data-path> <output.csv>` - build a reusable player-year feature table for every prospect row.
- `draft-room-intel evaluate-role-models <data-path> [--feature-output <csv>] [--model-output <csv>]` - fit pure-Python role-specific models and print their evaluation report.
- `draft-room-intel report-historical-validation <data-path> <output-dir>` - write a side-by-side historical outcome-validation report for draft-board scoring approaches.
- `draft-room-intel validate-eliteprospects <export.csv>` - inspect an Elite Prospects CSV export for required player/stat shape before import.
- `draft-room-intel scaffold-demo-class --draft-year <year>` - create the local raw/reference/processed/output layout and starter CSV templates for a single-class demo.
- `draft-room-intel audit-demo-class --draft-year <year>` - check whether a draft class has the minimum local source files for ETL and demo use.
- `python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py audit --draft-year <year>` - use the repo-local skill helper to scaffold, audit, stage raw inputs, run ETL, and build the demo for one class.
- `draft-room-intel build-demo-readiness <final-dataset-dir> <output-dir>` - build a self-contained demo site plus `reports/data_gaps` and `reports/modeling_sanity` artifacts in one command.
- `draft-room-intel report-demo-gaps <demo-output-dir> <report-output-dir>` - prioritize remaining low-evidence players after a demo build.
- `draft-room-intel report-demo-modeling <demo-output-dir> <report-output-dir>` - compare the demo board against consensus ordering and list largest movements.
- `draft-room-intel etl-draft-year <output-dir> --draft-year <year> --base-dir <base-dir> [--eliteprospects-csv <export.csv>]` - create a base ETL snapshot from an existing normalized dataset and optionally enrich it with Elite Prospects in one command.
- `draft-room-intel etl-draft-year <output-dir> --draft-year <year> --hockeydb-draft-html <path> [--eliteprospects-csv <export.csv>]` - generate the base dataset from a local HockeyDB draft HTML file, then optionally enrich it with Elite Prospects.
- `draft-room-intel etl-draft-year <output-dir> --draft-year <year> --hockeydb-draft-html <path> --hockeydb-player-pages-dir <dir> [--eliteprospects-csv <export.csv>]` - generate a richer base dataset from local HockeyDB draft and player-page HTML caches.
- `draft-room-intel process-eliteprospects <export.csv> <base-dir> <source-output-dir> <merged-output-dir> --draft-year <year>` - run the full Elite Prospects import, merge, quality report, and match-template workflow.

The current historical validation note is tracked in [`docs/historical_validation.md`](docs/historical_validation.md).
- `draft-room-intel import-eliteprospects <export.csv> <output-dir> --draft-year <year>` - convert a local Elite Prospects CSV export into normalized `players.csv` and `season_stat_lines.csv`.
- `draft-room-intel merge-eliteprospects <base-dir> <eliteprospects-dir> <output-dir>` - overlay normalized Elite Prospects player and stat rows onto a base draft-year dataset while preserving draft selections, rankings, and outcomes. Use `--match-map <csv>` for reviewed manual matches with `source_player_id,base_player_id,note`.
- `draft-room-intel generate-match-map-template <base-dir> <unmatched_source_players.csv> <output.csv>` - create a review CSV with closest base-player candidates for unmatched source rows.
- `draft-room-intel report-merge-quality <base-dir> <source-dir> <merged-dir>` - audit match rate, stat replacement, missing values, duplicates, and league coverage for a merged dataset.
- `python -m draft_room_intelligence.cli evaluate <csv> --baseline consensus` - evaluate the consensus baseline against a normalized historical CSV.
- `python -m draft_room_intelligence.cli evaluate <csv> --baseline projection` - evaluate the heuristic projection baseline against a normalized historical CSV.
- `python -m draft_room_intelligence.cli evaluate <csv-or-directory> --baseline adjusted-production` - evaluate the league- and role-adjusted production baseline.
- `python -m draft_room_intelligence.cli evaluate <csv-or-directory> --baseline hybrid` - evaluate the weighted hybrid baseline.
- `make test` - run the automated tests.
- `make lint` - run Ruff against `src` and `tests`.
- `make check` - run linting and tests.

The Makefile automatically uses `.venv/bin/python` when `.venv` exists. You can still override it with `make PYTHON=/path/to/python check`.

## Data Layout

- `data/raw/hockeydb/<year>/...` - local HockeyDB draft HTML input for base generation.
- `data/raw/hockeydb/<year>/player_pages/...` - optional cached HockeyDB player HTML pages for better bio and pre-draft stat extraction.
- `data/raw/eliteprospects_<year>.csv` - optional Elite Prospects export for enrichment.
- `data/processed/<year>/base` - normalized base dataset snapshot.
- `data/processed/<year>/eliteprospects` - normalized Elite Prospects import.
- `data/processed/<year>/final` - merged dataset used for evaluation and downstream modeling.
- `data/processed/pilot_2019` - current tracked pilot snapshot used for local evaluation and modeling examples.
- `data/reference/league_context.csv` - tracked league strength and context table used by adjusted production logic.

## Git Notes

- Track code, docs, tests, processed sample datasets, and reference tables.
- Keep raw exports and scraped HTML local under `data/raw/`; they are ignored by git.
- Keep one-off analysis artifacts under `outputs/`; they are ignored by git.
- If we later add larger processed datasets, we should decide explicitly whether they stay in git or move to external storage.

## Raw Input Contract

- Minimum local base input: one HockeyDB draft HTML file for the draft year.
- Better local base input: the draft HTML plus cached player pages keyed by normalized `player_id`.
- Optional enrichment input: one Elite Prospects CSV export for the same draft year.

## Current State

The project has moved past the original skeleton stage. Right now it supports:

1. draft-year ETL from local HockeyDB HTML,
2. optional enrichment from Elite Prospects CSV exports,
3. merge quality review and manual match-map support,
4. baseline evaluation on normalized player-year datasets,
5. reusable feature table generation,
6. simple role-specific model fitting and evaluation.

## Development Direction

Relevant next steps from here:

1. improve league coverage and consistency across junior, college, European, and pro contexts,
2. keep closing pre-draft stat gaps where external exports provide better history,
3. strengthen feature engineering around league quality, role, age, playoff context, and adult-league exposure,
4. compare fitted models against simpler board-order heuristics with better calibration and ranking diagnostics,
5. bring scouting-text and decision-support layers back into the pipeline once the data base is stronger.

## Core Design Principle

Keep three engines separate:

- Projection engine: how good is the player likely to become?
- Scouting intelligence engine: what do humans say, and where do they disagree?
- Decision optimization engine: given our picks and team context, what should we do?

This keeps numeric ranking reproducible while still using AI/NLP for evidence and explanation.
