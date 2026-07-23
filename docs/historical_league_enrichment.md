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
2022-2026. Swedish discovery reads official season selectors and cached season indexes instead
of maintaining tournament IDs by hand. The first historical proof covers 2024 J20
Nationell/SHL/HockeyAllsvenskan regular and playoff feeds; Liiga source rows are generated for
2014-2026. Protected KHL/MHL rows remain disabled and use reviewed open-CSV evidence as the
operational fallback.

USHL coverage uses separate skater and goalie feeds for regular seasons and playoffs. The public
HockeyTech season catalog supplies opaque season IDs, so no year mapping is maintained by hand.
The 2019-20 season correctly has no playoff sources.

CHL collection also uses HockeyTech as the machine-readable fallback for reviewed OHL, WHL, and
QMJHL season URLs. Each cache bundles the skater and goalie payloads while preserving the original
CHL URL as provenance. The adapter retains regular-season/playoff separation and goalie exposure.

## Commands

```bash
make historical-league-discover
make historical-ushl-catalog
make historical-ushl-discover
make historical-ncaa-discover
make historical-swehockey-catalogs
make historical-europe-discover
make historical-swehockey-feeds
make historical-league-cache
make historical-league-etl
```

`discover-chl-sources` reads official season selectors from cached CHL pages, resolves opaque
season IDs, and generates stable season-ID cache names. Existing validated cache paths remain
enabled. Missing historical caches are generated as disabled rows.

The CHL website currently returns HTTP 403 to the non-browser collector. For `chl` manifest rows,
the collector extracts the reviewed season ID and downloads the corresponding HockeyTech skater
and goalie feeds instead. A successful `collect-league-sources --include-disabled` run now enables
the validated source in the manifest automatically. Empty or invalid feeds remain disabled; this
correctly covers canceled stages such as the 2019-20 QMJHL playoffs.

`historical-ushl-catalog` caches the official season catalog. `historical-ushl-discover` merges
generated USHL rows into the existing manifest without replacing CHL or open-CSV sources. Once
the feeds are cached and discovery is rerun, validated files become enabled automatically.

The USHL adapter preserves skater scoring and goalie GP, minutes, shots, saves, goals against,
SV%, GAA, wins, losses, overtime losses, and shutouts. Regular-season and playoff lines remain
separate evidence rows. Draft-class enrichment reuses up to three cached prior USHL seasons, so
NTDP and club histories are not reduced to the draft-year feed. Skater and goalie feeds remain
distinct when historical sources are cloned.

`historical-swehockey-catalogs` caches official SHL, HockeyAllsvenskan, and J20/U20 season
indexes. `historical-europe-discover` then derives stable player-feed rows from those local
indexes. Discovery preserves European manifest rows outside a bounded year range. Junior
North/South, Top 10, and continuation phases are aggregated by player and team, while championship
playoffs remain separate evidence.

`historical-swehockey-feeds` collects only exact `swehockey:combined` rows. This provider filter
avoids retrying unrelated Liiga or protected Russian endpoints during a Swedish backfill. The
2019-20 SHL single-stage page and its reversed season label are handled explicitly; no playoff row
is generated for that canceled postseason.

NCAA and European adapters write `advanced_stat_lines.csv` beside the standard season table.
Each row includes games, plus/minus, shots, blocks, faceoff wins/losses, and faceoff percentage
when the source publishes them. Exact feed duplicates are removed before Swedish split phases
are combined, preserving auditable source URLs on the normalized row.

The 2025-2026 cache-first proof applies 18 NCAA/USHL feeds per class, including up to three prior
USHL seasons. After all enabled adapters and canonical duplicate reconciliation, the 2025 class
contains 846 stat rows, covers all 224 players, and has 16 low-evidence demo profiles. The 2026
class contains 497 stat rows and covers 175 of 223 players (78.5%); its remaining 48-player queue
is concentrated outside the cached NCAA/USHL feeds.

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
CHL matching starts with an accent-insensitive normalized name. It also recognizes a small reviewed
set of preferred/legal first-name variants and provider-redacted surnames only when the candidate
is unique inside the same league. Ambiguous identities are rejected. Every adapter writes a match
audit beside normalized tables. NCAA and USHL audits classify every player as `matched`,
`not_eligible`, `ambiguous_identity`, `unmatched_in_cached_source`, or `source_unavailable`, and
record whether the configured cache set was available, partial, or unavailable.

Class replacement is staged and atomic. A failed adapter leaves the prior `final` directory in
place. Source cache digests and baseline ETL state are recorded in
`league_enrichment_state.json`.

## Next Coverage Work

Populate reviewed regular-season and playoff sources in this order:

1. Run the Swehockey catalog/collection workflow for 2014-2023 and 2025-2026, then add Mestis and
   Finnish U20.
2. Add stable Canadian Junior A/B and US high-school sources.
3. Resolve the remaining explicit CHL transliteration aliases through a reviewed identity map.
4. NHL outcome snapshots for mature classes, kept separate from pre-draft features.

The CHL backlog is restored for played seasons across 2014-2026. The main structural exception is
the 2021 OHL draft cohort because the 2020-21 OHL season was canceled; those players require their
actual alternate-league evidence rather than synthetic OHL rows.

The report at `outputs/league_enrichment/summary.md` is the operational coverage baseline.
Run `audit-league-ingestion` after enrichment to refresh `year_summary.csv`, `issues.csv`, and
`coverage_gaps.csv`. The gap queue orders uncovered players by draft tier and records their
drafted-from league and source family, making it the input backlog for the next adapter pass.

The completed 2014-2026 Swehockey pass validates 114 feeds. Against the prior cross-year baseline,
it adds normalized pre-draft evidence for 217 players, reduces Nordic gaps from 460 to 243, and
adds advanced coverage for 218 players. The final audit checks exact duplicates and conflicting
skater, goalie, and advanced-stat keys. Remaining gaps are tracked by the standard audit rather
than inferred from source collection success.

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

The reviewed 2014 through 2024 packs extend the same workflow to earlier classes using official NHL
prospect bios and public player, league, team, and club media pages. These packs cover all
domestic Russian-league targets, including separate adult, junior, playoff, and goalie evidence.
The corrected audit treats `Russia Jr.` and
`RUSSIA-2` draft codes as domestic MHL/VHL pathways, preventing uncovered players from being
hidden in the external-league bucket. KHL, VHL, MHL, and playoff rows remain separate so adult
exposure and meaningful postseason runs survive feature aggregation.
