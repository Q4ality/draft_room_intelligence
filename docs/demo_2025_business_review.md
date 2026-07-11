# 2025 Business Demo Review

## Review Result

The current 2025 demo is ready for an internal or friendly business workflow demo.

It should be positioned as:

- draft-room preparation software,
- a board triage and disagreement workflow,
- an explainable source/evidence review layer,
- a recent-class showcase, not an outcome-validated prediction model.

## Verified Package

Rebuilt with:

```bash
make demo-2025-readiness
```

Output:

- Site: `outputs/demo_2025_openstats_russian_nordic_cleanup/index.html`
- Board rows: 224
- Dataset status: `strong`
- Data-gap report: `outputs/demo_2025_openstats_russian_nordic_cleanup/reports/data_gaps/summary.md`
- Modeling sanity report: `outputs/demo_2025_openstats_russian_nordic_cleanup/reports/modeling_sanity/summary.md`

Browser smoke check:

- page title loads as `Draft Room Intelligence Demo`
- 224 board rows render
- default detail opens on Michael Misa
- `Why Review` and `Review Flags` sections are visible
- shortlist export action is visible
- no browser console errors observed

## Strong Demo Stories

| Story | Player | Why it works |
| --- | --- | --- |
| Trust anchor | Michael Misa | Ranked sensibly at the top with high evidence and familiar OHL production. |
| Model-favored CHL forward | Cole Reschny | Board rank 6 vs consensus 18, with medium evidence and playoff share. |
| Goalie-specific signal | Alexei Medvedev | Board rank 33 vs consensus 47, high evidence, goalie metrics, multi-league history. |
| Multi-row US path | Charlie Cerrato | Six rows across USHL/USNTDP/NCAA, high evidence, model-higher discussion case. |
| Adult-league caution | Anton Frondell | Consensus rank 3 vs board rank 19, high evidence, adult exposure, clear review flag. |
| Consensus-higher defense | Max Psenicka | High evidence, adult/playoff exposure, but board is more cautious than consensus. |
| Russian credibility fix | Alexander Zharovsky | MHL production plus KHL playoff exposure; directly addresses prior data credibility issue. |
| Nordic coverage | Eric Nilson | High evidence with Swedish junior, adult, and playoff context. |
| Late-round model favorite | Roman Luttsev | Board rank 159 vs consensus 206, high evidence, useful shortlist story. |
| Adult Czech exposure | Vojtech Cihar | Full adult-league exposure and playoff row; good cross-league translation example. |

## Use With Care

- Michael Misa still has a `No adult-league sample` review flag. That is normal for a CHL player, but say it as a translation note, not a player concern.
- Roman Luttsev is a useful late-round target story, but his current sample has no playoff row captured.
- Pyotr Andreyanov is a good goalie comparison option, but still only medium evidence because he has two rows and no playoff signal.
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
7. Open Alexei Medvedev for goalie metrics.
8. Open Alexander Zharovsky or Eric Nilson for non-CHL credibility.
9. Add Roman Luttsev and one goalie to the shortlist.
10. Export shortlist CSV.
11. End with the data-gap report as the next operational loop.

## Current Demo Metrics

- Evidence depth: 50 high, 97 medium, 77 low
- Disagreement buckets: 95 aligned, 60 model higher, 69 consensus higher
- Average board-vs-consensus movement: 9.9 slots
- Players moved 10+ slots: 89
- 10+ slot moves with high/medium evidence: 70
- Top 50 overlap with consensus: 43 of 50

Interpretation:

The board is different enough from consensus to create discussion, but still anchored enough to feel credible. Most of the best demo movement cases have usable evidence.

## Remaining External-Demo Risks

1. **Data completeness:** 77 players are still low evidence.
2. **Source automation:** several enrichment packs are curated CSVs rather than fully automated source adapters.
3. **Recent-class validation:** 2025 cannot validate future NHL outcomes yet.
4. **European coverage:** Sweden, Finland, Russia, Czech, and goalie source coverage still need systematic adapters.
5. **UI polish:** the shell is functional, but source trace and compare explanation could be more polished for a paid-customer demo.

## Recommended Next Work

1. Run one targeted data pass against the highest-priority goalie and Sweden/USHL gaps.
2. Add a compact "demo mode" preset that preloads the recommended story players.
3. Improve source trace display in the player detail table so each stat row links more clearly to its source.
4. Add a one-page export/PDF summary for the shortlist.
5. Start historical validation with older classes once demo coverage is credible enough.
