# 2025 Demo Readiness

## Current Demo Package

Open the current demo shell from:

- `outputs/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats/index.html`

Current normalized dataset:

- `data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats/final`

Current export files:

- `outputs/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats/board.csv`
- `outputs/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats/compare.csv`
- `outputs/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats/players.json`
- `outputs/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats/manifest.json`

## What We Have

- Full 2025 drafted-player board: 224 players.
- Board, detail, compare, shortlist, and shortlist CSV export UX.
- Public consensus slot proxy and model-vs-consensus disagreement buckets.
- League-adjusted production, role group, age, size, handedness, adult exposure, playoff exposure, and evidence-depth fields in the demo export.
- Real source enrichment from Wikipedia draft data, Wikipedia bio/career pages, CHL official data, and USHL official data.
- Transparent evidence flags so weakly covered players are visible instead of hidden.

Latest manifest snapshot:

- `dataset_status`: `thin`
- evidence depth: 174 low, 28 medium, 22 high
- disagreement buckets: 162 aligned, 30 consensus higher, 32 model higher
- source coverage: 224 draft-slot proxies, 84 CHL players, 37 USHL players, 47 Wikipedia bio matches, 33 Wikipedia career-stat matches

Recent enrichment improvement:

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
   - Pick 8-12 players for the actual presentation.
   - Manually verify positions, league rows, ranking explanation, and risk flags for those players.

5. Demo framing polish
   - Replace scary interpretation of `thin` with clear "coverage in progress" language in the presenter talk track.
   - Keep the UI transparent, but explain that low evidence is an expected data-quality flag, not a model failure.

## Recommended Next Build Step

Before adding more model complexity, make the demo stronger by improving source coverage for the top missing leagues:

1. Sweden adapter for SHL/HockeyAllsvenskan/J20.
2. Finland adapter for Liiga/U20.
3. Russian-league fallback strategy using open pages that are not blocked by KHL challenge pages.
4. NCAA/USNTDP source enrichment.
5. A hand-checked featured-player CSV for the presentation route.

After that, rerun the demo export and use evidence-depth movement as the success metric.
