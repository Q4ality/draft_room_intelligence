# 2025 Demo Presenter Script

## Current Demo Package

Use the current strong demo build:

- Site: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/index.html`
- One-page meeting brief: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/meeting_brief.pdf`
- Printable HTML brief: `outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/meeting_brief.html`
- Dataset: `data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup_ep_pdf/final`

Current manifest snapshot:

- Players: 224
- Dataset status: `strong`
- Evidence depth: 138 high, 59 medium, 27 low
- Disagreement buckets: 80 aligned, 15 model higher, 129 consensus higher
- Source coverage: Wikipedia draft rows, draft-slot proxy, CHL, USHL, Wikipedia career rows, and curated open-stats packs
- Score posture: `model_score` remains production-sensitive, `board_score` blends model plus consensus and EP evidence, and `team_adjusted_score` adds organization fit.

## Business Narrative

Position the product as draft-room preparation software, not as a black-box draft oracle.

Demo line:

> This board turns fragmented public pre-draft histories into an explainable discussion workflow. We can see where the model agrees with consensus, where it disagrees, and whether the evidence behind each player is strong enough for a serious draft-room conversation.

## Seven-Minute Flow

1. Open the board and point to the dataset status and 224-player coverage.
2. Keep the one-page meeting brief available as the discussion agenda and leave-behind.
3. Select `Start Guided Demo`.
4. Use the arrow controls to move from Michael Misa to Matthew Schaefer and explain the three-score calibration.
5. Continue through Cole Reschny, Alexei Medvedev, Charlie Cerrato, and Anton Frondell.
6. Exit guided mode and filter by disagreement bucket for open exploration.
7. Add two players to the shortlist and export the shortlist CSV.
8. Close on the data-quality loop: evidence labels show what is ready and what still needs source enrichment.

The compact guided sequence is intentionally limited to six complementary stories. The longer `Guided Stories` list remains available for questions about Russian, Nordic, Czech, defense, and late-round coverage.

The readiness build regenerates both meeting-brief formats from the same bundle as the site. The PDF is constrained to one landscape page and uses goalie-specific SV%, GAA, record, and shutout evidence for goalie stories.

## Recommended Story Players

| Player | Why show him | Presenter note |
| --- | --- | --- |
| Michael Misa | Trust anchor at top of board | Board rank 2, consensus rank 2, high-evidence OHL scorer with multiple source rows. |
| Matthew Schaefer | Elite-defense calibration story | Board rank 3, consensus rank 1. Use him to explain why `model_score` can be lower for a 19-game sample while `board_score` stays top-tier. |
| Cole Reschny | CHL forward production story | Consensus rank 18, board rank 16. Shows league-adjusted production and playoff signal without overselling model independence. |
| Alexei Medvedev | Goalie evidence story | Consensus rank 47, board rank 49. Shows goalie-specific metrics and multi-row pre-draft history. |
| Charlie Cerrato | Model-higher NCAA/USHL path | Six history rows across USHL, USNTDP, and NCAA. Good example of why multi-row pre-draft histories matter. |
| Anton Frondell | Consensus-higher adult-league case | Consensus rank 3, board rank 15. Use as a cautious case: strong adult exposure, but the board does not simply copy consensus. |
| Max Psenicka | Consensus-higher defense case | Consensus rank 31, board rank 33. Shows how playoff/adult exposure can be visible while the board still flags disagreement. |
| Alexander Zharovsky | Russian multi-league credibility case | Carries MHL production plus KHL playoff exposure. This directly addresses the earlier demo credibility gap. |
| Eric Nilson | Nordic multi-row coverage case | High evidence, Swedish junior and playoff rows. Shows the new Nordic enrichment pass. |
| Roman Luttsev | Late-round model-favorite case | Consensus rank 206, board rank 159. Useful for the shortlist workflow and "late-round target" tag. |
| Vojtech Cihar | Adult Czech exposure case | High evidence with full adult-league exposure and playoff row. Good example of cross-league context. |

## Talk Track By Screen

### Board

Say:

> The board is not just a rank list. It is a triage surface. The rank is useful, but the key business value is the combination of model-vs-consensus disagreement and evidence depth.

Point out:

- `Dataset status: strong`
- evidence labels
- disagreement badges
- primary league and adult/playoff exposure columns

### Player Detail

Say:

> The detail page answers the first question a scouting director will ask: "Why did the system put him there, and can I trust the data behind it?"

Point out:

- why-high bullets
- risk flags
- Prospect Stats Evidence
- pre-draft history rows
- row-level source URLs
- goalie metrics when applicable

### Compare

Say:

> The compare view is where this becomes a meeting tool. It lets the room debate two or three players using the same normalized evidence instead of jumping between disconnected source pages.

Good compare pairs:

- Alexei Medvedev vs Pyotr Andreyanov for goalie evaluation
- Charlie Cerrato vs Shane Vansaghi for NCAA/USNTDP profile comparison
- Anton Frondell vs Alexander Zharovsky for adult-league exposure versus junior production
- Roman Luttsev vs Marco Mignosa for late-round model-favorite discussion

### Shortlist

Say:

> The shortlist is deliberately simple. The goal is not to replace the club's scouting system today; it is to turn model disagreement into a concrete review list that can be exported.

Suggested tags:

- `model favorite`
- `consensus favorite`
- `late-round target`
- `review`

## Honest Caveats

Use these proactively:

- The 2025 class is a recent-class showcase, not an outcome-validated predictive result.
- Evidence labels are part of the product: low evidence means "needs more source coverage", not "bad player".
- The strongest current coverage is CHL, USHL/NCAA samples, curated Russian/Nordic open stats, and selected Wikipedia career rows.
- Remaining data work should prioritize the 27 low-evidence players by demo importance and source availability.

## Demo Success Criteria

The demo is successful if the viewer understands three things:

1. The system can create a full-class board from fragmented public sources.
2. The board is inspectable through evidence, risk, and source traceability.
3. The workflow helps scouts find and discuss disagreement cases faster.
