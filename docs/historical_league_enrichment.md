# Historical League Enrichment

The draft-class ETL establishes one normalized identity and selection baseline per year. League
enrichment is a separate cache-first layer so source outages cannot make routine rebuilds
non-reproducible.

## Source Manifest

`data/reference/league_stat_sources.csv` contains one reviewed source per row:

- `draft_year`, `league`, and `season` define the target class and stat context.
- `adapter` selects `chl`, `ushl`, `ncaa`, `europe`, or `open_csv` parsing.
- `stage` preserves regular-season versus playoff evidence.
- `source_url` is provenance and the optional collection endpoint.
- `cache_path` is the ignored local artifact used by ETL.
- `source_label` identifies the provider/feed kind or stores the USHL season ID.

The generated manifest also records 18 NCAA feeds and a reviewed European source catalog. NCAA
uses USCHO structured pages for 2014-2021 and College Hockey Inc. skater/goalie tables for
2022-2026. The initial European slice covers 2025 Swedish J20/SHL/HockeyAllsvenskan and Liiga
regular/playoff feeds. Protected KHL/MHL rows remain disabled and use reviewed open-CSV evidence
as the operational fallback.

USHL coverage uses separate skater and goalie feeds for regular seasons and playoffs. The public
HockeyTech season catalog supplies opaque season IDs, so no year mapping is maintained by hand.
The 2019-20 season correctly has no playoff sources.

## Commands

```bash
make historical-league-discover
make historical-ushl-catalog
make historical-ushl-discover
make historical-ncaa-discover
make historical-europe-discover
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

`historical-ushl-catalog` caches the official season catalog. `historical-ushl-discover` merges
generated USHL rows into the existing manifest without replacing CHL or open-CSV sources. Once
the feeds are cached and discovery is rerun, validated files become enabled automatically.

The USHL adapter preserves skater scoring and goalie GP, minutes, shots, saves, goals against,
SV%, GAA, wins, losses, overtime losses, and shutouts. Regular-season and playoff lines remain
separate evidence rows.

NCAA and European adapters write `advanced_stat_lines.csv` beside the standard season table.
Each row includes games, plus/minus, shots, blocks, faceoff wins/losses, and faceoff percentage
when the source publishes them. Swedish split-phase rows do not replace an existing richer
full-season line, but their explicitly scoped advanced evidence is retained.

Use `collect-league-sources --adapter <name>` to refresh one provider family without retrying
the entire manifest. Rerun the corresponding discovery command after collection so validated
caches become enabled.

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
2. Extend Swedish/Finnish reviewed catalogs backward from the validated 2025 slice.
3. Add an authorized Russian cache/export path plus transliteration mapping for KHL/MHL/VHL.
4. NHL outcome snapshots for mature classes, kept separate from pre-draft features.

The report at `outputs/league_enrichment/summary.md` is the operational coverage baseline.

## Russian Coverage Iteration

Russian enrichment uses one reviewed source pack per draft year, for example
`data/reference/russian_open_stats_2024.csv` and `data/reference/russian_open_stats_2026.csv`.
Each row must retain its source URL and stage.
The pack is enabled through `league_stat_sources.csv` with the `open_csv` adapter, so it runs
inside the same atomic, fingerprinted class enrichment as NCAA, USHL, and other leagues.

After each enrichment pass, generate the next player-level review queue:

```bash
PYTHONPATH=src python -m draft_room_intelligence.cli audit-russian-coverage \
  data/processed/draft_classes/2026/final \
  outputs/russian_coverage/2026 \
  --draft-year 2026
```

The queue separates covered and missing Russian prospects and summarizes regular-season,
playoff, KHL, VHL, and MHL games. Repeat the same workflow for an earlier draft year by adding
its reviewed source pack and manifest row; no adapter code changes are required.

The reviewed 2020 through 2024 packs extend the same workflow to earlier classes using official NHL
prospect bios and public player, league, team, and club media pages. These packs cover all
domestic Russian-league targets, including separate adult, junior, playoff, and goalie evidence.
The corrected audit treats `Russia Jr.` and
`RUSSIA-2` draft codes as domestic MHL/VHL pathways, preventing uncovered players from being
hidden in the external-league bucket. KHL, VHL, MHL, and playoff rows remain separate so adult
exposure and meaningful postseason runs survive feature aggregation.
