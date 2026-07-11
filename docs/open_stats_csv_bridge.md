# Open Stats CSV Bridge

Use `enrich-open-stats-csv` when a league-specific site is blocked, unstable, or not worth a dedicated parser yet. The command overlays cleaned public stat rows onto an existing normalized dataset by matching player name plus league.

## Command

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli enrich-open-stats-csv \
  <base-final-dir> \
  <output-final-dir> \
  --source <csv_path>,<source_label>,<season>[,<league>][,regular|playoffs] \
  [--allow-new-leagues]
```

Example:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli enrich-open-stats-csv \
  data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs/final \
  data/processed/demo_2025_open_stats/final \
  --source data/reference/demo_2025_priority_open_stats.csv,curated-open-stats,2023-24,,regular \
  --allow-new-leagues
```

Use `--allow-new-leagues` only for curated rows that have been checked against player names. It allows rows such as a prior USHL/USNTDP season to be appended even when the current base row only lists NCAA.

## Expected Columns

The bridge accepts flexible aliases, but these canonical names are preferred:

- `name`
- `season`
- `league`
- `team`
- `games`
- `goals`
- `assists`
- `points`
- `regular_season`
- `source_id`
- `source_url`

Goalie columns:

- `goalie_minutes`
- `shots_against`
- `saves`
- `goals_against`
- `save_percentage`
- `goals_against_average`
- `wins`
- `losses`
- `ties`
- `shutouts`

## Source Strategy

Use this bridge for:

- NCAA / USNTDP tables from College Hockey Inc. or conference pages.
- Swedish/Finnish public stat exports copied into clean CSV.
- Russian KHL/MHL/VHL fallback exports when official pages are blocked.
- Manually verified showcase-player rows when automated collection is not ready.

The bridge is not a replacement for source-specific adapters. It is a fast path to improve demo data completeness while preserving provenance and keeping the ETL repeatable.
