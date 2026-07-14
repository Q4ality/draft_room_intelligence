# 2025 Business Demo Review

## Review Result

The current 2025 demo is ready for an internal or friendly business workflow demo.

It should be positioned as:

- draft-room preparation software,
- a board triage and disagreement workflow,
- an explainable source/evidence review layer,
- a recent-class showcase, not an outcome-validated prediction model.

## Verified Package

Current EP-PDF demo rebuilt with:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli build-demo-readiness \
  data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup_ep_pdf/final \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  --team-depth-csv outputs/org_team_depth_pre_2025_26_proxy_with_ahl/depth.csv \
  --gap-top-n 35 \
  --movement-top-n 40
```

Output:

- Site: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/index.html`
- Board rows: 224
- Dataset status: `strong`
- Data-gap report: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/data_gaps/summary.md`
- Modeling sanity report: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/modeling_sanity/summary.md`
- Demo sanity report: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/demo_sanity/summary.md`

Browser smoke check:

- page title loads as `Draft Room Intelligence Demo`
- 224 board rows render
- default detail opens on Michael Misa
- `Why Review` and `Review Flags` sections are visible
- `Prospect Stats Evidence` is visible in player detail
- goalie stat rows render as SV% / GAA in the neutral `Production` column
- shortlist export action is visible
- no browser console errors observed

## Ranking Explanation

- `model_score` remains production/stat-sensitive. It can be lower for shortened samples, goalies, or defense profiles whose value is not fully captured by point production.
- `board_score` blends model output with consensus rank, Elite Prospects guide evidence, and role-aware calibration. This is the primary demo board order.
- `team_adjusted_score` adds roster-fit context for the drafted or selected NHL organization.
- The current demo intentionally protects elite-consensus defense and goalie profiles from being buried behind scoring forwards. Matthew Schaefer is the clearest example: his pure model score is lower because the captured sample is only 19 games, but his board rank remains top-tier because consensus, EP evidence, role rank, and NYI team fit all support that.

## Strong Demo Stories

| Story | Player | Why it works |
| --- | --- | --- |
| Trust anchor | Michael Misa | Board rank 2, consensus 2, high evidence and familiar OHL production. |
| Elite defense calibration | Matthew Schaefer | Board rank 3 despite a lower pure model score; demonstrates consensus, EP evidence, and role-aware protection. |
| Model-favored CHL forward | Cole Reschny | Board rank 16 vs consensus 18, with high production and playoff context. |
| Goalie-specific signal | Alexei Medvedev | Board rank 49 vs consensus 47, goalie metrics, multi-league history, and source-visible evidence. |
| Multi-row US path | Charlie Cerrato | Six rows across USHL/USNTDP/NCAA, high evidence, model-higher discussion case. |
| Adult-league caution | Anton Frondell | Consensus rank 3 vs board rank 15, high evidence, adult exposure, clear review flag. |
| Consensus-higher defense | Max Psenicka | High evidence, adult/playoff exposure, but board remains more cautious than consensus. |
| Russian credibility fix | Alexander Zharovsky | MHL production plus KHL playoff exposure; directly addresses prior data credibility issue. |
| Nordic coverage | Eric Nilson | High evidence with Swedish junior, adult, and playoff context. |
| Late-round model favorite | Roman Luttsev | Board rank 159 vs consensus 206, high evidence, useful shortlist story. |
| Adult Czech exposure | Vojtech Cihar | Full adult-league exposure and playoff row; good cross-league translation example. |

## Use With Care

- Michael Misa still has a `No adult-league sample` review flag. That is normal for a CHL player, but say it as a translation note, not a player concern.
- Roman Luttsev is a useful late-round target story, but his current sample has no playoff row captured.
- Pyotr Andreyanov is a good goalie comparison option: 94 GP, .936 SV%, 2.19 GAA, 7 SO. He should still be framed as a goalie-evidence story, not as a finished outcome forecast.
- Low-evidence movement cases should not be used as confident recommendations.

## Business Narrative

Recommended opening:

> This is a board-meeting prep tool. It does not claim to replace scouts or predict the 2025 NHL outcome today. It turns fragmented public pre-draft information into a structured board, highlights where consensus and model evidence disagree, and makes every recommendation inspectable through source rows and coverage flags.

Recommended close:

> The value is not only the ranking. The value is reducing prep time, finding disagreement cases faster, and making data quality visible enough that scouts know which players need more review.

## Demo Flow To Use

1. Open the board and show `dataset_status: strong`.
2. Show full-class coverage: 224 players.
3. Open Michael Misa as a trust anchor.
4. Filter or sort to model-higher cases.
5. Open Cole Reschny or Charlie Cerrato.
6. Open Anton Frondell or Max Psenicka as a consensus-higher/caution case.
7. Open Matthew Schaefer to explain the three-score ranking model.
8. Open Alexei Medvedev or Pyotr Andreyanov for goalie metrics.
9. Open Alexander Zharovsky or Eric Nilson for non-CHL credibility.
10. Add Roman Luttsev and one goalie to the shortlist.
11. Export shortlist CSV.
12. End with the data-gap report as the next operational loop.

## Current Demo Metrics

- Evidence depth: 138 high, 59 medium, 27 low
- Disagreement buckets: 80 aligned, 15 model higher, 129 consensus higher
- Average board-vs-consensus movement: 13.8 slots
- Players moved 10+ slots: 135
- 10+ slot moves with high/medium evidence: 116
- Top 50 overlap with consensus: 50 of 50

Interpretation:

The board is now more consensus-anchored at the top while still surfacing evidence and team-fit differences in player detail. That is the safer posture for a recent-class business demo: the system explains disagreements without pretending to have outcome validation for 2025.

## Remaining External-Demo Risks

1. **Data completeness:** 27 players are still low evidence.
2. **Source automation:** several enrichment packs are curated CSVs rather than fully automated source adapters.
3. **Recent-class validation:** 2025 cannot validate future NHL outcomes yet.
4. **European coverage:** Sweden, Finland, Russia, Czech, and goalie source coverage still need systematic adapters.
5. **UI polish:** the shell is functional, but source trace, compare explanation, and calibration wording could be more polished for a paid-customer demo.

## Recommended Next Work

1. Systematize ranking calibration with tests instead of demo-only weights.
2. Run one targeted data pass against full 2026 coverage and the highest-priority European/NCAA gaps.
3. Improve team-fit analytics with U23 pipeline depth, NHL/AHL readiness separation, and contender/rebuild risk tolerance.
4. Add a compact "demo mode" preset that preloads the recommended story players.
5. Add a one-page export/PDF summary for the shortlist.
