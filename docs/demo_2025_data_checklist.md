# 2025 Data Acquisition Checklist

## Goal

Collect the minimum viable source package needed to run the 2025 draft-class demo through the current ETL and demo export pipeline.

## Required Files

### 1. HockeyDB Draft HTML

One local draft page for the 2025 class.

Recommended path:

- `data/raw/hockeydb/2025/nhl2025e.html`

Why it matters:

- provides the draft class roster
- provides draft slot proxy
- provides drafted-from team and league context

## Strongly Recommended Files

### 2. Cached HockeyDB Player Pages

One HTML page per featured player.

Recommended path:

- `data/raw/hockeydb/2025/player_pages/<player_id>.html`

Why it matters:

- better biographical data
- richer same-season pre-draft stat history
- improved evidence depth for player detail pages

### 3. Elite Prospects Export

One CSV export covering the same class.

Recommended path:

- `data/raw/eliteprospects_2025.csv`

Why it matters:

- richer league histories
- more multi-row pre-draft evidence
- better odds of surfacing adult and playoff context

## Nice-To-Have Files

### 4. Manual Match Map

If Elite Prospects merge has unresolved players:

- `data/reference/eliteprospects_2025_match_map.csv`

### 5. Hand-Checked Featured Prospect List

For the actual demo script, pick 6-10 players and verify their rows manually.

Suggested file:

- `data/reference/demo_2025_featured_players.csv`

Recommended fields:

- `player_id`
- `name`
- `demo_role`
- `notes`

## Minimum Demo Readiness Criteria

The 2025 class is usable for the demo if we have:

1. draft HTML available
2. at least 20-40 prospects with valid normalized rows
3. at least 6-10 featured players with checked evidence
4. enough rows to avoid most players landing in `evidence_depth = low`

The 2025 class is strong for the demo if we also have:

1. cached HockeyDB player pages for the featured set
2. Elite Prospects export merged in
3. visible multi-row histories
4. some adult exposure and playoff evidence in the featured set

## ETL Run Sequence

### Base ETL

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli etl-draft-year data/processed/demo_2025 \
  --draft-year 2025 \
  --hockeydb-draft-html data/raw/hockeydb/2025/nhl2025e.html \
  --hockeydb-player-pages-dir data/raw/hockeydb/2025/player_pages
```

### Enriched ETL

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli etl-draft-year data/processed/demo_2025 \
  --draft-year 2025 \
  --hockeydb-draft-html data/raw/hockeydb/2025/nhl2025e.html \
  --hockeydb-player-pages-dir data/raw/hockeydb/2025/player_pages \
  --eliteprospects-csv data/raw/eliteprospects_2025.csv
```

### Demo Export

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli export-demo-package \
  data/processed/demo_2025/final \
  outputs/demo_2025_package
```

## Data Review Checklist

Before presenting the demo, confirm:

- featured players have correct positions
- consensus ranks look plausible
- primary leagues are normalized correctly
- obvious adult-league profiles are tagged correctly
- `short_reason` and `risk_note` read naturally
- player detail pages show useful pre-draft history, not empty shells

## Current Status

As of July 10, 2026:

- the repo has a working demo export pipeline
- the repo does not appear to contain a real 2025 draft dataset yet
- the strongest local raw data found nearby is still 2019

That means the next gating item for a 2025 business demo is source collection, not more feature engineering.
