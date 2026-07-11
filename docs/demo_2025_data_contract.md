# 2025 Demo Data Contract

## Purpose

Define the UI-facing data shapes for the 2025 single-class demo.

This contract is intentionally thin:

- backend remains CSV-first internally,
- frontend consumes flattened board and player-detail payloads,
- no frontend logic should need to reconstruct hockey context from raw tables.

## Source Inputs

Expected backend inputs for the demo dataset:

- `players.csv`
- `draft_selections.csv`
- `season_stat_lines.csv`
- `rankings.csv`
- optional Elite Prospects overlay
- feature export from `export-feature-table`
- model/board export from `evaluate-role-models` or a dedicated board builder

## Dataset Inventory Checklist

Before building the demo, confirm the 2025 class has:

- draft HTML source available
- cached HockeyDB player pages available for showcase players
- Elite Prospects export available or explicitly unavailable
- enough players with multi-row pre-draft histories
- at least 20-40 players with credible evidence for demo use
- at least 6-10 featured players reviewed by hand

## Board Record

One board row per player.

```json
{
  "player_id": "2025-001-example-player",
  "draft_year": 2025,
  "board_rank": 1,
  "name": "Example Player",
  "position": "C",
  "role_group": "forward",
  "nationality": "CAN",
  "age_at_draft": 18.22,
  "height_cm": 185,
  "weight_kg": 84,
  "handedness": "L",
  "primary_league": "OHL",
  "primary_league_family": "Canadian Junior",
  "primary_competition_level": "junior",
  "consensus_rank": 4,
  "model_score": 0.742,
  "board_score": 0.768,
  "adjusted_production_score": 0.701,
  "adjusted_ppg": 1.184,
  "role_rank": 3,
  "role_percentile": 0.94,
  "adult_game_share": 0.000,
  "junior_game_share": 1.000,
  "college_game_share": 0.000,
  "pro_game_share": 0.000,
  "playoff_game_share": 0.122,
  "average_league_weight": 0.980,
  "pre_draft_row_count": 3,
  "pre_draft_league_count": 2,
  "evidence_depth": "medium",
  "consensus_delta": -3,
  "disagreement_bucket": "model_higher",
  "badges": ["Multi-League"],
  "short_reason": "Production stands out within role, Multiple league contexts",
  "risk_note": "No adult-league sample"
}
```

### Board Field Notes

- `board_rank`: final rank displayed in the board
- `model_score`: score from the chosen model or scoring blend
- `board_score`: final ordering score used by the demo
- `consensus_delta`: `consensus_rank - board_rank`
- `disagreement_bucket`:
  - `model_higher`
  - `consensus_higher`
  - `aligned`
- `evidence_depth`:
  - `low`
  - `medium`
  - `high`

Suggested rules:

- `high` if `pre_draft_row_count >= 3` or `pre_draft_league_count >= 2`
- `medium` if `pre_draft_row_count == 2`
- `low` otherwise

## Player Detail Record

One detail payload per player.

```json
{
  "player_id": "2025-001-example-player",
  "header": {
    "name": "Example Player",
    "position": "C",
    "role_group": "forward",
    "nationality": "CAN",
    "age_at_draft": 18.22,
    "height_cm": 185,
    "weight_kg": 84,
    "handedness": "L",
    "consensus_rank": 4,
    "board_rank": 1
  },
  "summary": {
    "board_score": 0.768,
    "model_score": 0.742,
    "adjusted_production_score": 0.701,
    "adjusted_ppg": 1.184,
    "role_rank": 3,
    "role_percentile": 0.94,
    "average_league_weight": 0.980,
    "adult_game_share": 0.000,
    "playoff_game_share": 0.122,
    "evidence_depth": "medium"
  },
  "why_high": [
    "Strong role-adjusted production relative to same-position peers.",
    "Multi-row pre-draft history gives better evidence depth.",
    "Primary competition context is credible for a first-round profile."
  ],
  "risk_flags": [
    "Limited adult-league exposure before draft.",
    "Production signal is concentrated in junior play."
  ],
  "pre_draft_history": [
    {
      "season": "2024-25",
      "league": "OHL",
      "team": "Example Team",
      "games": 58,
      "goals": 25,
      "assists": 41,
      "points": 66,
      "regular_season": true,
      "source": "hockeydb"
    }
  ],
  "sources": [
    {
      "source": "hockeydb",
      "source_id": "2025-001-example-player",
      "source_url": "https://www.hockeydb.com/"
    }
  ]
}
```

## Comparison Record

The compare view can reuse board records plus a smaller shared subset:

```json
{
  "player_id": "2025-001-example-player",
  "name": "Example Player",
  "position": "C",
  "consensus_rank": 4,
  "board_rank": 1,
  "board_score": 0.768,
  "adjusted_production_score": 0.701,
  "role_percentile": 0.94,
  "primary_league": "OHL",
  "average_league_weight": 0.980,
  "adult_game_share": 0.000,
  "junior_game_share": 1.000,
  "college_game_share": 0.000,
  "playoff_game_share": 0.122,
  "age_at_draft": 18.22,
  "height_cm": 185,
  "weight_kg": 84,
  "handedness": "L",
  "evidence_depth": "medium"
}
```

## Explanation Generation Rules

Current demo should use rule-based explanation text derived from existing features.

### Positive explanation examples

- mention `adult_game_share` when greater than `0.15`
- mention `role_percentile` when greater than `0.90`
- mention `average_league_weight` when greater than `1.0`
- mention `pre_draft_league_count` when greater than `1`
- mention `playoff_game_share` when greater than `0.08`

### Risk explanation examples

- mention low evidence when `pre_draft_row_count == 1`
- mention junior-only profile when `adult_game_share == 0`
- mention limited playoff signal when `playoff_game_share == 0`
- mention large disagreement when `abs(consensus_delta) >= 10`

## Suggested Export Files

For a first demo implementation, generate:

- `outputs/demo_2025_board.csv`
- `outputs/demo_2025_players.json`
- `outputs/demo_2025_compare.csv`

If JSON export is not yet implemented, CSV-first is acceptable as long as the fields above are available.

## Next Backend Tasks

1. add a dedicated demo export command
2. compute `board_rank`, `consensus_delta`, `disagreement_bucket`, and `evidence_depth`
3. generate rule-based `short_reason` and `risk_note`
4. optionally emit one JSON blob per player for detail pages
