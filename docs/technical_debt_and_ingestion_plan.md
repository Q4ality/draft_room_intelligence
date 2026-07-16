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
- The current team-fit snapshot is a pre-2025/26 proxy plus 2024-25 AHL data, not a verified historical opening-night roster.
- `pytest` is not installed in the active shell used during this session, so tests were limited to `compileall`, CLI smoke checks, and artifact assertions.

Needs cleanup before productization:

- Demo calibration weights should move from hard-coded board rules into a tested calibration layer.
- League-specific ingestion should move from curated CSV packs to cache-first source adapters with fixtures.
- Name matching and duplicate stat-row reconciliation need stronger audits for non-English names, transliteration, and multi-source conflicts.
- Elite Prospects PDF extraction needs a cost-aware model-routing layer. The current latest-model vision path is useful for hard pages, but too expensive as the default for full-guide extraction.
- Historical validation needs older draft classes with NHL outcome labels before predictive claims are made.

## Systematic Ingestion Architecture

Use a four-stage ingestion contract for every source family:

1. **Collect** raw source files into `data/raw/<source>/<year>/` or an equivalent ignored cache. Live fetches should be optional; cached HTML/CSV/PDF should be enough to rerun ETL.
2. **Parse** source-specific files into normalized source tables with `players.csv`, `rankings.csv` when applicable, and `season_stat_lines.csv`.
3. **Merge** source tables into the draft-year base dataset through reviewed identity matching and reconciliation reports.
4. **Audit** coverage, duplicates, conflict fields, evidence-depth movement, and story-player sanity before rebuilding the demo.

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
   - Acceptance: Francesco Dell'Elce, Adam Benak, Zack Sharp, and similar US-path profiles have multi-row histories with stable source provenance.

4. **Swedish/Finnish adapter pass**
   - Goal: normalize SHL, HockeyAllsvenskan, J20 Nationell, Liiga, Mestis, and U20 rows consistently.
   - Acceptance: Swedish/Finnish low-evidence clusters shrink and adult exposure is explicitly classified.

5. **Russian KHL/MHL/VHL and goalie pass**
   - Goal: improve Russian skater and goalie rows without depending on blocked official pages as the only source.
   - Acceptance: MHL/KHL/VHL rows preserve source provenance, playoff/adult exposure, and goalie SV%/GAA/SO where available.

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
