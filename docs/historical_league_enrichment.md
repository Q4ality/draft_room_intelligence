# Historical League Enrichment

The draft-class ETL establishes one normalized identity and selection baseline per year. League
enrichment is a separate cache-first layer so source outages cannot make routine rebuilds
non-reproducible.

## Source Manifest

`data/reference/league_stat_sources.csv` contains one reviewed source per row:

- `draft_year`, `league`, and `season` define the target class and stat context.
- `adapter` selects `chl`, `ushl`, or `open_csv` parsing.
- `stage` preserves regular-season versus playoff evidence.
- `source_url` is provenance and the optional collection endpoint.
- `cache_path` is the ignored local artifact used by ETL.
- `source_label` identifies an open CSV provider or stores the USHL season ID.

The generated manifest records 73 CHL regular-season/playoff sources for 2014-2026. Six
validated 2025 caches are enabled. The remaining 67 discovered rows are disabled until a valid
cache can be collected; keeping them tracked makes the backlog exact rather than implicit.

## Commands

```bash
make historical-league-discover
make historical-league-cache
make historical-league-etl
```

`discover-chl-sources` reads official season selectors from cached CHL pages, resolves opaque
season IDs, and generates stable season-ID cache names. Existing validated cache paths remain
enabled. Missing historical caches are generated as disabled rows.

The CHL website currently returns HTTP 403 to the non-browser collector. Browser rendering can
pass the site challenge, but the browser security boundary does not expose the underlying page
source for staging. An authorized environment can retry the full backlog explicitly with
`collect-league-sources --include-disabled`; ordinary collection only checks enabled sources and
therefore remains deterministic and green.

The equivalent enrichment command is:

```bash
PYTHONPATH=src python -m draft_room_intelligence.cli enrich-draft-range-leagues \
  data/reference/league_stat_sources.csv \
  data/processed/draft_classes \
  outputs/league_enrichment \
  --project-root . --start-year 2014 --end-year 2026
```

The runner leaves years without configured sources visible as `not_configured`. A configured
year is `blocked` when its cache is absent, `completed` after application, and
`skipped_complete` when its source fingerprint has not changed.

## Matching And Safety

League adapters use both existing stat leagues and the official NHL draft selection's
`drafted_from_league` field. This allows an empty historical class to gain its first stat row.
Matching remains exact after normalized-name comparison and is rejected when two class players
share the same normalized name. Every adapter writes a match audit beside normalized tables.

Class replacement is staged and atomic. A failed adapter leaves the prior `final` directory in
place. Source cache digests and baseline ETL state are recorded in
`league_enrichment_state.json`.

## Next Coverage Work

Populate reviewed regular-season and playoff sources in this order:

1. CHL (OHL, WHL, QMJHL) for 2014-2024 and 2026.
2. USHL/USNTDP and NCAA for all classes.
3. Sweden, Finland, Russia, and other European development/adult leagues through curated open
   CSV adapters until stable official APIs are available.
4. NHL outcome snapshots for mature classes, kept separate from pre-draft features.

The report at `outputs/league_enrichment/summary.md` is the operational coverage baseline.
