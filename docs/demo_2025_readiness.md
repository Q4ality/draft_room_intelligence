# 2025 Demo Readiness

## Current Demo Package

Open the current demo shell from:

- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/index.html`

Current normalized dataset:

- `data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup_ep_pdf/final`

Current export files:

- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/board.csv`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/compare.csv`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/players.json`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/manifest.json`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/data_gaps/summary.md`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/modeling_sanity/summary.md`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_sanity/summary.md`
- `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance/summary.md`

Rebuild the full local package with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli build-demo-readiness \
  data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup_ep_pdf/final \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  --team-depth-csv outputs/org_team_depth_pre_2025_26_proxy_with_ahl/depth.csv \
  --gap-top-n 35 \
  --movement-top-n 40
```

Equivalent Make target:

```bash
make demo-2025-readiness
```

## What We Have

- Full 2025 drafted-player board: 224 players.
- Board, detail, compare, shortlist, shortlist CSV export, and one-page shortlist summary HTML export UX.
- Prospect Stats Evidence in player detail, including goalie-specific SV%/GAA/SO display.
- Public consensus slot proxy and model-vs-consensus disagreement buckets.
- League-adjusted production, role group, age, size, handedness, adult/playoff exposure, sample-size-weighted adult/playoff evidence, and evidence-depth fields in the demo export.
- Team-fit analytics now separate raw U25 depth into NHL-ready U25 and AHL/prospect U25 pipeline signals, so franchise-fit explanations are less likely to overstate need when a system already has young players in the same role.
- NHL membership now comes from official 2024-25 club-stat participants rather than the current roster endpoint. Cross-organization NHL/AHL collisions are assigned using each player's latest official game date; unresolved collisions are retained and labeled low-confidence instead of silently favoring one league.
- Contract opportunity is available as a guarded team-fit component. It remains neutral in the current demo because a historical contract/cap source has not yet been staged.
- Team-fit pipeline need is capped by fixed position-level U25 capacity and NHL/AHL readiness, so an empty role subtype cannot bypass a crowded organizational pipeline.
- Real source enrichment from Wikipedia draft data, Wikipedia bio/career pages, CHL official regular-season/playoff data, CHL goalie exposure, USHL official data, and curated open-stat packs for Russian, Nordic, NCAA/USHL, Czech, and selected cleanup targets.
- Transparent evidence flags so weakly covered players are visible instead of hidden.

Latest manifest snapshot:

- `dataset_status`: `strong`
- evidence depth: 27 low, 59 medium, 138 high
- disagreement buckets: 80 aligned, 129 consensus higher, 15 model higher
- current board sanity: top-50 overlap with consensus is 50 of 50, with Matthew Schaefer top-tier after role-aware calibration.
- demo acceptance: 11 of 11 checks passing, including full board/detail coverage, Prospect Stats Evidence, goalie evidence visibility, and neutral `Production` history labeling.
- team-fit payloads now include same-position NHL-ready U25, AHL U25, and non-NHL U25 pipeline counts in team options and team-view role gaps.

Recent enrichment improvement:

- Russian, Nordic, cleanup open-stat packs, and EP-PDF overlay now lift the current package to 737 stat lines.
- High-evidence players moved to 138 in the current EP-PDF package.
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

6. Point-in-time roster and contract coverage
   - The current view is a historical season-participation snapshot, not a verified draft-night reserve list.
   - Historical cap hit, contract term, and trade protection need a licensed or cached source export before contract opportunity becomes active.

## Recommended Next Build Step

Before adding more model complexity, make the demo stronger by improving source coverage for the top missing leagues:

1. Keep the current 2025 demo frozen for the review unless a blocking UI/data issue appears.
2. Build systematic source adapters using the collect-parse-merge-audit loop in [technical_debt_and_ingestion_plan.md](technical_debt_and_ingestion_plan.md).
3. Start with CHL cleanup if top-board credibility is the review concern; start with full 2026 EP guide extraction if scalability is the review concern.
4. Follow with NCAA/USHL/USNTDP, Swedish/Finnish, and Russian KHL/MHL/VHL passes.
5. Continue using evidence-depth movement and demo sanity reports as acceptance checks.

After that, rerun the demo export and use evidence-depth movement as the success metric.

Detailed implementation stories are tracked in [data_enrichment_stories.md](data_enrichment_stories.md). The current presentation flow is tracked in [demo_2025_presenter_script.md](demo_2025_presenter_script.md).

The latest business-demo review is tracked in [demo_2025_business_review.md](demo_2025_business_review.md).

The current prioritized data-gap report is tracked in [demo_2025_gap_report.md](demo_2025_gap_report.md). It is rebuilt by `build-demo-readiness`, or independently with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-gaps \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/data_gaps \
  --top-n 35
```

The current board-vs-consensus sanity report is tracked in [demo_2025_modeling_sanity.md](demo_2025_modeling_sanity.md). It is rebuilt by `build-demo-readiness`, or independently with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-modeling \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/modeling_sanity \
  --top-n 40
```

The focused demo sanity report is rebuilt by `build-demo-readiness`, or independently with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-sanity \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_sanity
```

The business-demo acceptance gate is rebuilt by `build-demo-readiness`, or independently with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-acceptance \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_acceptance
```
