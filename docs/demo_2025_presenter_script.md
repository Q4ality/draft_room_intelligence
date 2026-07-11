# 2025 Demo Presenter Script

## Current Demo Package

Use the current strong demo build:

- Site: `outputs/demo_2025_openstats_russian_nordic_cleanup/index.html`
- Dataset: `data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup/final`

Current manifest snapshot:

- Players: 224
- Dataset status: `strong`
- Evidence depth: 50 high, 97 medium, 77 low
- Disagreement buckets: 95 aligned, 60 model higher, 69 consensus higher
- Source coverage: Wikipedia draft rows, draft-slot proxy, CHL, USHL, Wikipedia career rows, and curated open-stats packs

## Business Narrative

Position the product as draft-room preparation software, not as a black-box draft oracle.

Demo line:

> This board turns fragmented public pre-draft histories into an explainable discussion workflow. We can see where the model agrees with consensus, where it disagrees, and whether the evidence behind each player is strong enough for a serious draft-room conversation.

## Seven-Minute Flow

1. Open the board and point to the dataset status.
2. Show that the class is complete: 224 drafted players.
3. Filter or sort by disagreement bucket.
4. Open one aligned top prospect to establish trust.
5. Open one model-higher player to show the value of normalized evidence.
6. Open one consensus-higher player to show where the tool is cautious.
7. Open one goalie and one European/Russian player to show non-CHL coverage.
8. Add two players to the shortlist and export the shortlist CSV.
9. Close on the data-quality loop: evidence labels show what is ready and what still needs source enrichment.

## Recommended Story Players

| Player | Why show him | Presenter note |
| --- | --- | --- |
| Michael Misa | Trust anchor at top of board | High-evidence OHL scorer with multiple source rows. Use this first so the room sees familiar names ranked sensibly. |
| Cole Reschny | Model-higher CHL forward | Consensus rank 18, board rank 6. Shows league-adjusted production and playoff signal moving a player into the discussion. |
| Alexei Medvedev | Model-higher goalie | Consensus rank 47, board rank 33, high evidence after cleanup. Shows goalie-specific metrics and multi-row pre-draft history. |
| Charlie Cerrato | Model-higher NCAA/USHL path | Six history rows across USHL, USNTDP, and NCAA. Good example of why multi-row pre-draft histories matter. |
| Anton Frondell | Consensus-higher adult-league case | Consensus rank 3, board rank 19. Use as a cautious case: strong adult exposure, but the board does not simply copy consensus. |
| Max Psenicka | Consensus-higher defense case | Consensus rank 46, board rank 82. Shows how playoff/adult exposure can be visible while the board still flags disagreement. |
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
- Remaining data work should prioritize the 77 low-evidence players by demo importance and source availability.

## Demo Success Criteria

The demo is successful if the viewer understands three things:

1. The system can create a full-class board from fragmented public sources.
2. The board is inspectable through evidence, risk, and source traceability.
3. The workflow helps scouts find and discuss disagreement cases faster.
