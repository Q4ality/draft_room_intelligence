# 2025 Business Demo Review

## Review Result

The current 2025 demo is ready for an internal or friendly business workflow demo.

It should be positioned as:

- draft-room preparation software,
- a board triage and disagreement workflow,
- an explainable source/evidence review layer,
- a recent-class showcase, not an outcome-validated prediction model.

## Verified Package

Current reviewed demo rebuilt with:

```bash
PYTHONPATH=src python -m draft_room_intelligence.cli build-demo-year 2025
```

Output:

- Site: `outputs/demo_2025_reproducible/index.html`
- Board rows: 224
- Dataset status: `strong`
- Data-gap report: `outputs/demo_2025_reproducible/reports/data_gaps/summary.md`
- Modeling sanity report: `outputs/demo_2025_reproducible/reports/modeling_sanity/summary.md`
- Demo sanity report: `outputs/demo_2025_reproducible/reports/demo_sanity/summary.md`

Previously recorded browser smoke check (repeat on the current build before presenting):

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
- `board_score` blends model output with reference rank, Elite Prospects guide evidence, and role-aware calibration. The legacy `consensus_rank` field can include actual draft positions; it is not an independent consensus or predictive benchmark.
- `team_adjusted_score` adds roster-fit context for the drafted or selected NHL organization.
- Team-fit context now separates NHL-ready U25 players from AHL/prospect U25 pipeline depth before scoring and explaining organizational fit.
- Reference and scouting inputs influence the ordering of defense and goalie profiles as well as forwards. Matthew Schaefer remains board rank 3; this is a historical calibration example, not evidence of an independent forecast.

## Strong Demo Stories

| Story | Player | Why it works |
| --- | --- | --- |
| Familiar OHL example | Michael Misa | Board 2, reference 2; aligned, high depth. |
| Defense calibration | Matthew Schaefer | Board 3, reference 1; aligned. Explain reference/scouting dependence. |
| CHL forward production | Cole Reschny | Board 15, reference 18; aligned. Inspect playoff context. |
| Goalie-specific evidence | Alexei Medvedev | Board 50, reference 47; aligned. Inspect goalie metrics and sources. |
| Multi-row US path | Charlie Cerrato | Board 53, reference 49; aligned. Inspect separate competition rows. |
| Adult-league context | Anton Frondell | Board 10, reference 3; aligned under the 8-slot threshold. |
| Defense evidence | Max Psenicka | Board 33, reference 31; aligned. Inspect adult/playoff evidence. |
| Russian multi-league evidence | Alexander Zharovsky | Board 36, reference 34; aligned. Inspect MHL/KHL sources. |
| Nordic coverage | Eric Nilson | Board 59, reference 45; reference higher. |
| Late-round historical difference | Roman Luttsev | Board 187, reference 206; model higher. Useful for shortlisting. |
| Adult Czech exposure | Vojtech Cihar | Board 82, reference 59; reference higher. |

Rebuild and verify these values in the manifest before presenting. All six primary stories are
aligned; use the backup cases to demonstrate a material reference difference.

## Use With Care

- Michael Misa still has a `No adult-league sample` review flag. That is normal for a CHL player, but say it as a translation note, not a player concern.
- Roman Luttsev is a useful late-round target story, but his current sample has no playoff row captured.
- Pyotr Andreyanov is a goalie comparison option. Inspect the current role-specific evidence in the generated package before quoting any aggregate statistic; this is not an outcome forecast.
- Low-evidence movement cases should not be used as confident recommendations.

## Business Narrative

Recommended opening:

> This historical board supports review meetings through source-linked player evidence and
> comparisons. Reference ranks can include actual draft outcomes, so this demonstrates a
> workflow rather than independent predictive performance.

Recommended close:

> The value is not only the ranking. The value is reducing prep time, finding disagreement cases faster, and making data quality visible enough that scouts know which players need more review.

## Demo Flow To Use

1. Open the board and show `dataset_status: strong`.
2. Show full-class coverage: 224 players.
3. Open Michael Misa as a trust anchor.
4. Filter or sort to model-higher cases.
5. Open Roman Luttsev for a model-higher historical difference; Cole Reschny and Charlie Cerrato are aligned evidence examples.
6. Open Eric Nilson or Vojtech Cihar for a reference-higher example.
7. Open Matthew Schaefer to explain the three-score ranking model.
8. Open Alexei Medvedev or Pyotr Andreyanov for goalie metrics.
9. Open Alexander Zharovsky or Eric Nilson for non-CHL credibility.
10. Add Roman Luttsev and one goalie to the shortlist.
11. Export shortlist CSV.
12. End with the data-gap report as the next operational loop.

## Current Demo Metrics

- Evidence depth: 178 high, 30 medium, 16 low
- Canonical baseline: 224 players and 846 pre-draft season-stat rows; verify the current fingerprint and board metrics in the generated `baseline.json`.
- Disagreement buckets: 76 aligned, 21 model higher, 127 reference higher
- Average board-reference movement: 14.3 slots
- Players moved 10+ slots: 136
- 10+ slot moves with high/medium evidence: 122
- Top 50 overlap with the historical reference: 50 of 50

Interpretation:

The board retains reference inputs, including historical outcomes. Agreement with that reference
must not be interpreted as predictive validation. Evidence and team-context views demonstrate
the review workflow and retain their stated limitations.

## Remaining External-Demo Risks

1. **Data completeness:** the canonical baseline currently reports 16 low-evidence players; rebuild the readiness artifacts before presenting this count externally.
2. **Source automation:** several enrichment packs are curated CSVs rather than fully automated source adapters.
3. **Recent-class validation:** 2025 cannot validate future NHL outcomes yet.
4. **European coverage:** Sweden, Finland, Russia, Czech, and goalie source coverage still need systematic adapters.
5. **UI polish:** the shell is functional, but source trace, compare explanation, and calibration wording could be more polished for a paid-customer demo.

## Recommended Next Work

1. Systematize ranking calibration with tests instead of demo-only weights.
2. Run one targeted data pass against full 2026 coverage and the highest-priority European/NCAA gaps.
3. Advance the official 2024-25 season-participation view to a point-in-time draft-night rights snapshot and stage audited contract/cap coverage.
4. Keep the guided-story preset and its presenter notes synchronized with the generated manifest.
5. Keep the existing one-page HTML/PDF brief and its provenance checks in the release validation.
