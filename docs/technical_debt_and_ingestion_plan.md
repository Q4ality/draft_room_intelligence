# Technical Debt And Systematic Data Ingestion Plan

This note separates pre-demo risks from product debt. The current 2025 demo is credible for an internal or friendly business review, but the platform still needs a more systematic ingestion layer before it should be sold as a repeatable multi-class product.

## Pre-Demo Technical Debt

Acceptable for tomorrow morning's review:

- The 2025 demo uses a recent class, so ranking quality is sanity-checked against consensus rather than validated against NHL outcomes.
- Some source enrichment is still curated through cleaned open-stat CSV packs.
- Ranking calibration is demo-board logic, not a fully validated historical model.
- Generated demo artifacts live under `outputs/` and are regenerated locally rather than tracked in git.

Needs cleanup before an external paid-customer demo:

- Several readiness and presenter docs can drift from generated outputs unless they are rebuilt from report artifacts.
- Source trace is available, but row-level provenance still needs a cleaner UI treatment.
- The team-fit snapshot now uses official 2024-25 NHL club-stat participants and resolves cross-organization NHL/AHL rows by the latest official game date. It is still a season-participation view rather than a point-in-time draft-night reserve-list snapshot.
- `pytest` is not installed in the active shell used during this session, so tests were limited to `compileall`, CLI smoke checks, and artifact assertions.

Needs cleanup before productization:

- Demo calibration weights should move from hard-coded board rules into a tested calibration layer.
- League-specific ingestion should move from curated CSV packs to cache-first source adapters with fixtures.
- Name matching and duplicate stat-row reconciliation need stronger audits for non-English names, transliteration, and multi-source conflicts.
- Elite Prospects PDF extraction needs a cost-aware model-routing layer. The current latest-model vision path is useful for hard pages, but too expensive as the default for full-guide extraction.
- Contract/cap enrichment now includes a raw-export normalizer, historical snapshot checks, row-level matching audit, and neutral missing-data behavior. It still needs a permitted dated source export or API credential; do not scrape around provider access controls or terms.
- Historical validation needs older draft classes with NHL outcome labels before predictive claims are made.

## Systematic Ingestion Architecture

The 2014-2026 orchestration foundation is implemented. Official NHL draft lists are cached locally, normalized into one class directory per year, checked for referential integrity, and resumed through `etl-draft-range`. See `docs/historical_class_etl.md`.

The remaining scaling problem is enrichment depth rather than draft-list coverage: 11 of 13 generated classes still have zero pre-draft season-stat rows, while the existing 2019 and 2025 datasets retain their richer histories.

The league-source orchestration layer is now implemented through
`data/reference/league_stat_sources.csv`. It applies cached CHL, USHL, NCAA, European, and curated open CSV
sources across class directories, fingerprints inputs for resumability, and reports exact
player coverage. CHL catalog discovery now covers 73 source rows across 2014-2026. Six cached
2025 rows are enabled; 67 historical rows are a disabled, retryable backlog because direct
collection receives HTTP 403 and browser-rendered page source cannot be exported through the
available browser security boundary. Prefer a permitted HockeyTech export/API or an authorized
cache-building environment over browser table scraping.

Use a four-stage ingestion contract for every source family:

1. **Collect** raw source files into `data/raw/<source>/<year>/` or an equivalent ignored cache. Live fetches should be optional; cached HTML/CSV/PDF should be enough to rerun ETL.
2. **Parse** source-specific files into normalized source tables with `players.csv`, `rankings.csv` when applicable, and `season_stat_lines.csv`.
3. **Merge** source tables into the draft-year base dataset through reviewed identity matching and reconciliation reports.
4. **Audit** coverage, duplicates, conflict fields, evidence-depth movement, and story-player sanity before rebuilding the demo.

Run `make historical-league-audit` after enrichment. Its year summary makes low-coverage classes visible, while `issues.csv` separates source conflicts, partial advanced-stat samples, and relevant unmatched source rows for review.

The reusable player-year feature table now consumes normalized advanced statistics under schema version 1 and applies sample-weighted, role-specific signals. Current limits remain explicit: advanced coverage is sparse outside NCAA and Nordic sources, plus/minus is contextual evidence rather than a standalone value metric, and demo ranking calibration does not yet retrain automatically when new advanced rows arrive.

The tracked source-family manifest is `data/reference/ingestion_source_families.csv`. Rebuild the audit with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-ingestion-plan \
  data/reference/ingestion_source_families.csv \
  outputs/ingestion_plan
```

Every new adapter should include:

- cached fixture input,
- parser unit test,
- source summary counts,
- unmatched-player report where identity matching is non-trivial,
- source URLs or source IDs on every stat row,
- regular-season/playoff separation when available,
- goalie metrics in goalie-specific fields rather than point proxies.

## Source-Family Priorities

1. **Full 2026 EP guide extraction**
   - Goal: create a complete 2026 normalized source package rather than sample/smoke outputs.
   - Acceptance: prospect-stat audit covers the full guide, with top skaters and goalies visible in `outputs/prospect_stats_2026`.
   - Technical debt: optimize extraction cost by routing pages through deterministic PDF text parsing first, cheaper extraction/classification models second, and latest vision models only for unresolved pages or fields.

2. **CHL cleanup pass**
   - Goal: close the highest-ranked remaining low-evidence CHL players: Carter Bear, Lynden Lakovic, Quinn Beauchesne, Parker Holmes, Luke Vlooswyk, Alexander Weiermair, and Charlie Paquette.
   - Acceptance: playoff/regular rows are present where available and low-evidence CHL skater/playoff gaps materially shrink.

3. **NCAA/USHL/USNTDP adapter pass**
   - Goal: move beyond curated packs for US development paths.
   - Current: USHL is covered for 2014-2026; NCAA uses USCHO for 2014-2021 and College Hockey Inc. for 2022-2026. USNTDP-only reconciliation remains.

4. **Swedish/Finnish adapter pass**
   - Goal: normalize SHL, HockeyAllsvenskan, J20 Nationell, Liiga, Mestis, and U20 rows consistently.
   - Current: official 2025 Swedish and Liiga regular/playoff feeds are validated. Historical source-ID catalogs, Mestis, and Finnish U20 remain.

5. **Russian KHL/MHL/VHL and goalie pass**
   - Goal: improve Russian skater and goalie rows without depending on blocked official pages as the only source.
   - Current: the cache parser/manifest contract exists, but KHL/MHL return HTTP 403 to the collector. Reviewed open CSV remains the fallback; VHL discovery and Cyrillic-to-English identity mapping remain technical debt.

6. **NHL organization contracts and cap context**
   - Goal: distinguish roster presence from organizational commitment and mobility.
   - Inputs: cap hit, contract end year, years remaining, contract type, and NTC/NMC or modified trade protection.
   - Scoring rule: contract evidence is a small team-fit component; missing coverage is neutral, and trade protection affects roster flexibility rather than player quality.
   - Acceptance: at least 80% NHL contract coverage, audited identity matches, snapshot dates, and no current-season contract rows presented as historical draft-night facts.
   - Current blocker: no permitted 2025-06-01 league-wide export is staged. The available open Kaggle candidate was rejected because its contract fields include post-draft updates despite being paired with 2024-25 statistics.

## Near-Term Execution Order

1. Keep the current 2025 demo frozen for tomorrow's review unless a blocking UI/data issue appears.
2. After review, pick one source family and run the full collect-parse-merge-audit loop instead of adding another one-off CSV.
3. Start with CHL cleanup if the review focuses on top-board credibility; start with 2026 EP guide extraction if the review asks for future-class scalability.
4. Rebuild `make demo-2025-readiness` after every ingestion pass and compare:
   - low-evidence count,
   - high/medium evidence count,
   - top-50 sanity,
   - story-player checks,
   - demo acceptance checks,
   - duplicate/conflict reports.

## Success Metrics

- Low-evidence players in the 2025 demo stay at or below the current 27 and decrease with each source-family pass.
- Every new source adapter can be rerun from cached files without network access.
- Every high-impact player detail has traceable stat rows and role-appropriate production display.
- The top board remains explainable through `model_score`, `board_score`, and `team_adjusted_score`.
- `report-demo-acceptance` passes after each ingestion or calibration change.
- Historical validation becomes the basis for model-quality claims; recent-class demos remain framed as workflow and evidence-readiness showcases.
