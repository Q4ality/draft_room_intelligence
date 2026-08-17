# Historical NHL Outcome Ingestion

The outcome source family uses official NHL public JSON endpoints. Raw responses are cached under
`data/raw/nhl_outcomes/<draft_year>/` and are never treated as model labels directly.

```bash
PYTHONPATH=src python -m draft_room_intelligence.cli collect-nhl-outcomes \
  data/raw/nhl_outcomes --draft-year 2019 --start-pick 1 --end-pick 25
```

The collector caches the draft payload, name-search responses, and player landing records. A player
is marked `matched` only when its landing record reports the same draft year and overall pick as the
official draft row. Ambiguous or unmatched names remain in `player_matches.csv` for review.
The command is resumable in pick ranges: each batch merges its results into the same audit file.

For an operational backfill, advance every configured year evenly with a bounded batch:

```bash
PYTHONPATH=src python -m draft_room_intelligence.cli collect-nhl-outcome-range \
  data/raw/nhl_outcomes --start-year 2014 --end-year 2021 --batch-size 10
```

Run the range command repeatedly. Each run starts at the first unreviewed pick for each year, so it
is safe to stop and resume. Keep batches small enough to respect the API and execution environment.

After matching, a separate parser must aggregate NHL regular-season rows only through each declared
June 30 horizon and write the canonical outcome-label schema. Current/career totals and unresolved
matches must never enter a retrospective label file.

```bash
PYTHONPATH=src python -m draft_room_intelligence.cli build-nhl-outcome-labels \
  data/raw/nhl_outcomes data/processed/outcome_labels --draft-year 2019 \
  --snapshot-dir data/processed/pilot_2019
```
