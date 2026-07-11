# 2025 Demo Readiness

## Current Demo Package

Open the current demo shell from:

- `outputs/demo_2025_openstats_russian_nordic_cleanup/index.html`

Current normalized dataset:

- `data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup/final`

Current export files:

- `outputs/demo_2025_openstats_russian_nordic_cleanup/board.csv`
- `outputs/demo_2025_openstats_russian_nordic_cleanup/compare.csv`
- `outputs/demo_2025_openstats_russian_nordic_cleanup/players.json`
- `outputs/demo_2025_openstats_russian_nordic_cleanup/manifest.json`
- `outputs/demo_2025_openstats_russian_nordic_cleanup/reports/data_gaps/summary.md`
- `outputs/demo_2025_openstats_russian_nordic_cleanup/reports/modeling_sanity/summary.md`

Rebuild the full local package with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli build-demo-readiness \
  data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup/final \
  outputs/demo_2025_openstats_russian_nordic_cleanup \
  --gap-top-n 35 \
  --movement-top-n 40
```

Equivalent Make target:

```bash
make demo-2025-readiness
```

## What We Have

- Full 2025 drafted-player board: 224 players.
- Board, detail, compare, shortlist, and shortlist CSV export UX.
- Public consensus slot proxy and model-vs-consensus disagreement buckets.
- League-adjusted production, role group, age, size, handedness, adult exposure, playoff exposure, and evidence-depth fields in the demo export.
- Real source enrichment from Wikipedia draft data, Wikipedia bio/career pages, CHL official regular-season/playoff data, CHL goalie exposure, USHL official data, and curated open-stat packs for Russian, Nordic, NCAA/USHL, Czech, and selected cleanup targets.
- Transparent evidence flags so weakly covered players are visible instead of hidden.

Latest manifest snapshot:

- `dataset_status`: `strong`
- evidence depth: 77 low, 97 medium, 50 high
- disagreement buckets: 95 aligned, 69 consensus higher, 60 model higher
- source coverage: 224 draft-slot proxies, 84 CHL players, 37 USHL players, 47 Wikipedia bio matches, 33 Wikipedia career-stat matches, and 41 players with open-stats source rows

Recent enrichment improvement:

- Russian, Nordic, and cleanup open-stat packs now lift the demo from 384 to 457 stat lines, with open-stats rows moving from 17 to 114.
- High-evidence players moved from 27 in the first open-stats baseline to 50 in the current cleanup package.
- Examples: Alexei Medvedev, Max Psenicka, Shane Vansaghi, Charlie Cerrato, Matthew Gard, Nathan Behm, Vojtech Cihar, Hayden Paupanekis, Tommy Lafreniere, Eric Nilson, Milton Gastrin, Roman Luttsev, and Alexander Zharovsky now carry richer histories.
- CHL true-playoff enrichment now adds regular and playoff rows separately instead of using playoff-team regular-season pages.
- CHL goalie exposure is now loaded from official CHL goalie tables.
- Examples: Ben Kindel, Cole Reschny, Justin Carbonneau, Joshua Ravensbergen, Jack Ivankovic, and Lucas Beckman now move from low evidence to medium evidence.
- Wikipedia career-stat enrichment now appends additional same-season leagues instead of only replacing the drafted-from placeholder row.
- Example: Alexander Zharovsky now carries both his 2024-25 MHL Tolpar Ufa row and his KHL Salavat Yulaev Ufa playoff row.
- PuckPedia parsing support has been added for cached/browser-saved player pages. Direct server-side HTTP fetches currently receive `403 Forbidden`, so bulk PuckPedia collection needs a browser-backed collector or saved HTML cache.

## Business Demo Positioning

This is ready for a workflow demo if we position it honestly:

- The product can ingest a recent draft class.
- It can normalize cross-league evidence into a draft board.
- It can surface players where model evidence disagrees with consensus.
- It can open a player detail view that explains the ranking and shows data confidence.
- It can support a shortlist/export loop for draft-room review.

The right narrative is:

> "This is a working draft-room workflow with transparent coverage flags. The value is the decision workflow and explainability; the remaining work is expanding source adapters so more players move from low to medium/high evidence."

## What We Miss

The main missing pieces are data coverage, not the demo shell.

1. Broader source adapters
   - Sweden: SHL, HockeyAllsvenskan, J20 Nationell
   - Finland: Liiga, Mestis, U20 SM-sarja
   - Russia: KHL, VHL, MHL
   - NCAA and USNTDP splits
   - AHL and other adult North American exposure
   - PuckPedia browser-backed/cached-page collection for extra tournament, NTDP, and career stat rows

2. Better multi-row pre-draft histories
   - Many players still have one usable stat row.
   - The detail page is strongest when a player has junior plus playoff, adult, or multi-league history.

3. Per-row source provenance in the UI
   - The normalized files retain source-specific match outputs.
   - The player-detail history still needs cleaner row-level source labels instead of broad mixed-source display.

4. Hand-checked showcase set
   - A first presenter set is now documented in [demo_2025_presenter_script.md](demo_2025_presenter_script.md).
   - Still verify the final UI rendering and presenter notes before an external meeting.

5. Demo framing polish
   - Replace scary interpretation of `thin` with clear "coverage in progress" language in the presenter talk track.
   - Keep the UI transparent, but explain that low evidence is an expected data-quality flag, not a model failure.

## Recommended Next Build Step

Before adding more model complexity, make the demo stronger by improving source coverage for the top missing leagues:

1. NCAA/USHL/USNTDP source enrichment.
2. Sweden adapter for SHL/HockeyAllsvenskan/J20.
3. Finland adapter for Liiga/U20.
4. Russian-league fallback strategy using open pages that are not blocked by KHL challenge pages.
5. Goalie-specific stat schema and demo presentation.

After that, rerun the demo export and use evidence-depth movement as the success metric.

Detailed implementation stories are tracked in [data_enrichment_stories.md](data_enrichment_stories.md). The current presentation flow is tracked in [demo_2025_presenter_script.md](demo_2025_presenter_script.md).

The latest business-demo review is tracked in [demo_2025_business_review.md](demo_2025_business_review.md).

The current prioritized data-gap report is tracked in [demo_2025_gap_report.md](demo_2025_gap_report.md). It is rebuilt by `build-demo-readiness`, or independently with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-gaps \
  outputs/demo_2025_openstats_russian_nordic_cleanup \
  outputs/demo_2025_openstats_russian_nordic_cleanup_gaps \
  --top-n 35
```

The current board-vs-consensus sanity report is tracked in [demo_2025_modeling_sanity.md](demo_2025_modeling_sanity.md). It is rebuilt by `build-demo-readiness`, or independently with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-modeling \
  outputs/demo_2025_openstats_russian_nordic_cleanup \
  outputs/demo_2025_openstats_russian_nordic_cleanup_modeling \
  --top-n 40
```
