# Draft-Room Decision Intelligence

Python prototype for an explainable draft and roster decision-intelligence workflow.

The current wedge is NHL draft analysis: build normalized pre-draft datasets, enrich them with external exports, compare baseline approaches, and evaluate simple role-specific models.

## Repository Layout

- `docs/project_brief.md` - source project/development draft.
- `docs/technical_debt_and_ingestion_plan.md` - current technical debt register and systematic ingestion roadmap.
- `docs/historical_class_etl.md` - scalable 2014-2026 draft-class collection, ETL, and integrity workflow.
- `docs/historical_league_enrichment.md` - cache-first league-stat enrichment and coverage reporting.
- `src/draft_room_intelligence/data/` - ETL, import, merge, and normalized table loading.
- `src/draft_room_intelligence/evaluation/` - baseline scoring and reporting utilities.
- `src/draft_room_intelligence/modeling/` - reusable feature table generation and role-specific models.
- `src/draft_room_intelligence/projection/` - projection helpers and production adjustment logic.
- `src/draft_room_intelligence/optimization/` - draft-board and team-fit scoring.
- `src/draft_room_intelligence/reports/` - Markdown player card generation.
- `tests/` - CLI, ETL, merge, and evaluation coverage.
- `data/reference/` - tracked reference tables such as league context.
- `data/reference/ingestion_source_families.csv` - source-family ingestion manifest for cache-first adapter planning.
- `data/reference/draft_class_etl.csv` - per-class path and source manifest for 2014-2026 batch ETL.
- `data/reference/league_stat_sources.csv` - reviewed league-stat URL/cache manifest.
- `data/reference/codex_routing_benchmark_tasks.csv` - repeatable benchmark tasks for measuring routing impact.
- `data/reference/codex_usage_run_log_template.csv` - local run-log template for routing usage measurements.
- `data/reference/codex_context_routes.csv` - bounded context route map for common Codex task types.
- `data/reference/codex_task_routing.csv` - task-level routing rules for context route, GPT-5.6 model, agent, reasoning, and validation selection.
- `data/processed/` - tracked sample/pilot normalized datasets.
- `data/raw/` - local raw inputs such as HockeyDB HTML and Elite Prospects exports. Ignored by git.
- `outputs/` - local exports from feature tables, model runs, and ad hoc analysis. Ignored by git.
- `skills/` - authored repo-local Codex skills for project context, validation, ingestion debugging, and demo-data preparation.
- `.agents/skills/` - symlink discovery layer so Codex can load repo skills from the standard location.
- `.codex/` - project-scoped Codex config and custom agents for bounded exploration and high-assurance review.

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
make team-depth-sample
make nhl-roster-sample
make ep-pdf-sample
make historical-draft-etl
make historical-league-etl
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
python -m draft_room_intelligence.cli import-nhl-rosters outputs/nhl_rosters_sample.csv --teams NYI --roster-json-dir tests/fixtures/nhl_api --stats-json-dir tests/fixtures/nhl_api
python -m draft_room_intelligence.cli import-nhl-rosters outputs/nhl_rosters_20242025.csv --season 20242025 --cache-json-dir data/raw/rosters/nhl/20242025
python -m draft_room_intelligence.cli merge-roster-csvs outputs/org_rosters_2024_25_with_ahl.csv outputs/nhl_rosters_20242025.csv outputs/ahl_rosters_2024_25.csv --resolve-cross-org-assignments --nhl-season 20242025 --assignment-cache-dir data/raw/rosters/assignment_logs/20242025
python -m draft_room_intelligence.cli normalize-roster-snapshot data/raw/rosters/rights/2025-06-01/rights_raw.csv data/raw/rosters/rights/2025-06-01/rights_normalized.csv --snapshot-date 2025-06-01 --metadata-json data/raw/rosters/rights/2025-06-01/rights_raw.metadata.json --audit-csv outputs/roster_snapshot_normalization_audit.csv
python -m draft_room_intelligence.cli build-point-in-time-roster outputs/org_rosters_2024_25_with_ahl.csv data/raw/rosters/rights/2025-06-01/rights_normalized.csv outputs/org_rosters_2025_06_01_rights.csv --snapshot-date 2025-06-01 --audit-csv outputs/roster_snapshot_build_audit.csv
python -m draft_room_intelligence.cli enrich-roster-contracts outputs/org_rosters_2024_25_with_ahl.csv data/raw/contracts/nhl_contracts_2025.csv outputs/org_rosters_2024_25_with_ahl_contracts.csv --audit-csv outputs/nhl_contract_match_audit.csv
python -m draft_room_intelligence.cli report-team-depth tests/fixtures/team_rosters_sample.csv outputs/team_depth_sample
python -m draft_room_intelligence.cli import-eliteprospects-pdf data/raw/draftdata/Draft25.pdf outputs/ep_pdf_2025_sample --draft-year 2025 --page-start 29 --page-end 80 --profile-limit 10
OPENAI_API_KEY=... python -m draft_room_intelligence.cli import-eliteprospects-pdf data/raw/draftdata/Draft26.pdf outputs/ep_pdf_2026_vision --draft-year 2026 --page-start 36 --page-end 64 --profile-limit 10 --vision-missing-tool-grades --pdftoppm-path /path/to/pdftoppm
python -m draft_room_intelligence.cli build-demo-readiness data/processed/draft_classes/2025/final outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf --team-depth-csv outputs/org_team_depth_2024_25_with_ahl/depth.csv
python -m draft_room_intelligence.cli validate-eliteprospects data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli etl-draft-year data/processed/etl_2019 --draft-year 2019 --base-dir data/processed/pilot_2019 --eliteprospects-csv data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli etl-draft-year data/processed/etl_2019 --draft-year 2019 --hockeydb-draft-html data/raw/hockeydb/2019/nhl2019e.html --eliteprospects-csv data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli etl-draft-year data/processed/etl_2019 --draft-year 2019 --hockeydb-draft-html data/raw/hockeydb/2019/nhl2019e.html --hockeydb-player-pages-dir data/raw/hockeydb/2019/player_pages --eliteprospects-csv data/raw/eliteprospects_2019.csv
python -m draft_room_intelligence.cli collect-nhl-draft-range data/raw/nhl_draft --start-year 2014 --end-year 2026
python -m draft_room_intelligence.cli etl-draft-range data/reference/draft_class_etl.csv outputs/draft_range_etl --project-root . --start-year 2014 --end-year 2026
python -m draft_room_intelligence.cli collect-league-sources data/reference/league_stat_sources.csv --project-root . --start-year 2014 --end-year 2026
python -m draft_room_intelligence.cli enrich-draft-range-leagues data/reference/league_stat_sources.csv data/processed/draft_classes outputs/league_enrichment --project-root . --start-year 2014 --end-year 2026
python -m draft_room_intelligence.cli process-eliteprospects data/raw/eliteprospects_2019.csv data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep --draft-year 2019
python -m draft_room_intelligence.cli import-eliteprospects data/raw/eliteprospects_2019.csv data/processed/eliteprospects_2019 --draft-year 2019
python -m draft_room_intelligence.cli merge-eliteprospects data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep
python -m draft_room_intelligence.cli generate-match-map-template data/processed/pilot_2019 data/processed/pilot_2019_ep/unmatched_source_players.csv data/reference/eliteprospects_2019_match_map_template.csv
python -m draft_room_intelligence.cli merge-eliteprospects data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep --match-map data/reference/eliteprospects_2019_match_map.csv
python -m draft_room_intelligence.cli report-merge-quality data/processed/pilot_2019 data/processed/eliteprospects_2019 data/processed/pilot_2019_ep
python -m pytest
```

The package exposes the same CLI as `draft-room-intel` after editable install.

## Local Environment

Copy `.env.example` to `.env` and put private local credentials there. `.env` is ignored by git.

```bash
OPENAI_API_KEY=sk-...
OPENAI_VISION_MODEL=gpt-5.6
PDFTOPPM_PATH=/Users/Sergei_Smirnov1/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pdftoppm
```

The CLI reads `.env` by default. For another file, pass `--env-file path/to/file` to
`import-eliteprospects-pdf`.

## Development Workflow

- `make install-dev` - install the project in editable mode with development tools.
- `make demo` - run the sample projection, scouting, team-fit, and player-card flow.
- `make demo-2025-readiness` - rebuild the current EP-PDF-enriched 2025 demo site, data-gap report, modeling sanity report, and demo sanity report.
- `make validate-pilot-2019` - compare consensus, production, hybrid, and role-aware scoring approaches against 2019 NHL outcomes.
- `make team-depth-sample` - build a sample NHL/AHL organizational role-depth report from normalized roster rows.
- `make nhl-roster-sample` - import cached NHL roster/stat JSON into roster rows, then build a team-depth report.
- `make ep-pdf-sample` - parse a limited local Elite Prospects draft-guide PDF window into normalized player/stat/profile artifacts.
- `make historical-draft-cache` - cache official NHL draft lists for 2014-2026; this target requires network access only for uncached years.
- `make historical-draft-etl` - build or resume all configured 2014-2026 normalized class datasets and write integrity reports.
- `make historical-league-cache` - collect missing league-stat files from the reviewed source manifest; CHL rows use a validated HockeyTech fallback when public CHL pages reject automation.
- `make historical-league-discover` - regenerate CHL season/stage URLs from cached official catalogs.
- `make historical-ncaa-discover` - generate NCAA source rows with the USCHO historical fallback.
- `make historical-swehockey-catalogs` - cache official Swedish season indexes for scalable historical feed discovery.
- `make historical-swehockey-feeds` - collect only discovered Swehockey feeds without retrying other European providers.
- `make historical-europe-discover` - merge reviewed Swedish, Finnish, and Russian source rows.
- `make historical-league-etl` - apply cached league sources and write per-class coverage reports.
- `make historical-league-audit` - report cross-year coverage, conflicting rows, partial advanced samples, and relevant source-match misses.
- `make historical-league-pipeline` - resolve source discovery, apply ready caches, and produce enrichment plus data-quality reports in one resumable run; add `--collect` to the underlying CLI command when network collection is intended.
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
- `draft-room-intel import-nhl-rosters <output.csv> [--teams NYI ...] [--season 20242025] [--cache-json-dir <dir>]` - import current rosters or historical season participants, resolve traded players to their final team from official game logs, and cache NHL payloads.
- `draft-room-intel enrich-roster-contracts <roster.csv> <contracts.csv> <output.csv>` - overlay cap hit, term, contract type, and trade protection from a cached contract export with match auditing.
- `draft-room-intel report-team-depth <roster.csv> <output-dir>` - build NHL/AHL role-depth and scarcity artifacts from normalized roster rows.
- `draft-room-intel import-eliteprospects-pdf <guide.pdf> <output-dir> --draft-year <year>` - extract local Elite Prospects draft-guide profile pages into normalized players, stat lines, rankings, and PDF sidecar tables.
- `draft-room-intel import-eliteprospects-pdf ... --vision-missing-tool-grades` - optionally render pages and use OpenAI vision to fill missing tool-grade values; requires `OPENAI_API_KEY` and Poppler `pdftoppm`.
- `draft-room-intel validate-eliteprospects <export.csv>` - inspect an Elite Prospects CSV export for required player/stat shape before import.
- `draft-room-intel scaffold-demo-class --draft-year <year>` - create the local raw/reference/processed/output layout and starter CSV templates for a single-class demo.
- `draft-room-intel audit-demo-class --draft-year <year>` - check whether a draft class has the minimum local source files for ETL and demo use.
- `python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py audit --draft-year <year>` - use the repo-local skill helper to scaffold, audit, stage raw inputs, run ETL, and build the demo for one class.
- `draft-room-intel build-demo-readiness <final-dataset-dir> <output-dir>` - build a self-contained demo site, a one-page HTML/PDF meeting brief, canonical `baseline.json`, plus `reports/data_gaps`, `reports/modeling_sanity`, `reports/demo_sanity`, and `reports/demo_acceptance` artifacts in one command. Acceptance fails when generated artifacts disagree with the baseline fingerprint or metrics.
- `draft-room-intel report-demo-gaps <demo-output-dir> <report-output-dir>` - prioritize remaining low-evidence players after a demo build.
- `draft-room-intel report-demo-modeling <demo-output-dir> <report-output-dir>` - compare the demo board against consensus ordering and list largest movements.
- `draft-room-intel report-demo-sanity <demo-output-dir> <report-output-dir>` - write top-board, top-role, biggest-disagreement, and story-player checks for demo validation.
- `draft-room-intel report-demo-acceptance <demo-output-dir> <report-output-dir>` - run pass/fail checks that guard the business-demo board shape and evidence UI.
- `draft-room-intel report-ingestion-plan data/reference/ingestion_source_families.csv <output-dir>` - audit cache, normalized output, docs, and tests for each planned ingestion source family.
- `draft-room-intel audit-league-ingestion data/processed/draft_classes <output-dir> --start-year 2014 --end-year 2026` - build the normalized league-data quality baseline and prioritized `coverage_gaps.csv` backlog used after ingestion runs.
- `draft-room-intel report-codex-usage <run-log.csv> <output-dir>` - build a Markdown/CSV/HTML dashboard comparing baseline vs routed Codex task runs.
- `draft-room-intel audit-codex-routing <output-dir>` - verify project Codex config, custom agents, and repo skill discovery links.
- `draft-room-intel report-codex-context-routes data/reference/codex_context_routes.csv <output-dir>` - audit bounded context routes used to reduce broad repo reads.
- `draft-room-intel report-codex-task-routing data/reference/codex_task_routing.csv data/reference/codex_context_routes.csv <output-dir>` - audit task-level routing rules for context route, agent, reasoning, and validation selection.
- `draft-room-intel route-codex-task "<task>" [--task-id <route>] [--phase discovery|implementation|validation|review|full] [--format markdown|json|shell]` - deterministically select a phase-aware route and print the exact `codex exec` command.
- `draft-room-intel run-codex-task "<task>" [--task-id <route>] [--phase discovery|implementation|validation|review|full]` - execute the selected phase route and append exact Codex JSON usage to `outputs/codex_usage/run_log.csv`.
- `draft-room-intel report-codex-telemetry <output-dir> --project-root <path>` - report historical local model/thread selection from `~/.codex/state_5.sqlite` without treating cumulative thread counters as cost.
- `draft-room-intel etl-draft-year <output-dir> --draft-year <year> --base-dir <base-dir> [--eliteprospects-csv <export.csv>]` - create a base ETL snapshot from an existing normalized dataset and optionally enrich it with Elite Prospects in one command.
- `draft-room-intel etl-draft-year <output-dir> --draft-year <year> --nhl-draft-json <picks.json>` - generate a normalized base dataset from cached official NHL draft picks.
- `draft-room-intel collect-nhl-draft-range <cache-dir> --start-year 2014 --end-year 2026` - cache official draft lists for offline ETL.
- `draft-room-intel etl-draft-range data/reference/draft_class_etl.csv <report-dir> --project-root .` - plan or execute resumable multi-class ETL with per-class integrity reporting.
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
- `data/raw/nhl_draft/<year>/picks.json` - cached official NHL draft-list baseline.
- `data/raw/hockeydb/<year>/player_pages/...` - optional cached HockeyDB player HTML pages for better bio and pre-draft stat extraction.
- `data/raw/eliteprospects_<year>.csv` - optional Elite Prospects export for enrichment.
- `data/processed/<year>/base` - normalized base dataset snapshot.
- `data/processed/<year>/eliteprospects` - normalized Elite Prospects import.
- `data/processed/<year>/final` - merged dataset used for evaluation and downstream modeling.
- `data/processed/draft_classes/<year>/final` - standardized 2014-2026 batch-ETL snapshots.
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
