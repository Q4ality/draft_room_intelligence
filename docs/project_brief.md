# Draft-Room Decision Intelligence

Working brief for the draft intelligence prototype.

## Current Scope

- Build normalized pre-draft player-year tables for a draft class.
- Enrich the base dataset with Elite Prospects exports when available.
- Evaluate simple baselines and role-specific models against downstream NHL outcomes.
- Keep the pipeline explainable enough for scouting and decision-support workflows.

## Current Data Flow

1. Local HockeyDB draft HTML provides the base draft class.
2. Optional cached HockeyDB player pages add better biographical and stat coverage.
3. Optional Elite Prospects CSV exports expand pre-draft league history.
4. ETL writes normalized tables used by evaluation, EDA, and modeling commands.

## Near-Term Focus

1. Tighten repo hygiene and reproducibility.
2. Continue feature engineering around league context, role, and exposure quality.
3. Re-run EDA and model evaluation after each material data improvement.

## Active Backlog

Current data-enrichment implementation stories are maintained in [data_enrichment_stories.md](data_enrichment_stories.md).
The generic fallback contract for cleaned public stat tables is documented in [open_stats_csv_bridge.md](open_stats_csv_bridge.md).
