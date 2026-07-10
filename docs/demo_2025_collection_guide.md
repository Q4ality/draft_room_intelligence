# 2025 Demo Collection Guide

## Goal

Collect the smallest real source package needed to turn the current demo shell into a real 2025 draft-class walkthrough.

## What We Need

### 1. HockeyDB draft page

Save the 2025 draft page HTML as:

- `data/raw/hockeydb/2025/nhl2025e.html`

This is the one file the current pipeline needs before it can produce a base class.

### 2. HockeyDB player pages

For the players you expect to feature in the demo, save their player pages into:

- `data/raw/hockeydb/2025/player_pages/`

One file per player is enough to start. This improves the player detail view and pre-draft stat history.

### 3. Elite Prospects export

Export a CSV for the same class and place it at:

- `data/raw/eliteprospects_2025.csv`

Minimum useful fields in the export:

- `EP Player ID`
- `Player`
- `Date of Birth`
- `Nation`
- `Position`
- `Shoots`
- `Height (cm)`
- `Weight (kg)`
- `Draft Age`
- `Season`
- `League`
- `Team`
- `GP`
- `G`
- `A`
- `TP`
- `URL`

If the export also includes `Stage`, keep it. That helps with playoff context.

## Useful Commands

Create the local structure:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli scaffold-demo-class --draft-year 2025
```

Check what is still missing:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli audit-demo-class --draft-year 2025
```

Build the normalized class once the files are present:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli etl-draft-year data/processed/demo_2025 \
  --draft-year 2025 \
  --hockeydb-draft-html data/raw/hockeydb/2025/nhl2025e.html \
  --hockeydb-player-pages-dir data/raw/hockeydb/2025/player_pages \
  --eliteprospects-csv data/raw/eliteprospects_2025.csv
```

Build the demo site:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli build-demo-site \
  data/processed/demo_2025/final \
  outputs/demo_2025
```

## Suggested First Featured Players Pass

As soon as the base class exists, populate:

- `data/reference/demo_2025_featured_players.csv`

Start with 6-10 players across a few story types:

- one top consensus forward
- one top consensus defenseman
- one goalie or specialist case if available
- one player with adult-league exposure
- one player with strong playoff evidence
- one disagreement case where model and consensus pull apart

## Practical Note

Right now the project is blocked by source availability, not by ETL or demo code. Once the three raw inputs are in place, the remaining work becomes much faster and more concrete.
