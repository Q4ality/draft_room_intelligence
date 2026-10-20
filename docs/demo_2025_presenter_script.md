# 2025 Demo Presenter Script

## Current Demo Package

Use the current strong demo build:

- Site: `outputs/demo_2025_reproducible/index.html`
- One-page meeting brief: `outputs/demo_2025_reproducible/meeting_brief.pdf`
- Printable HTML brief: `outputs/demo_2025_reproducible/meeting_brief.html`
- Dataset: `data/demo_snapshots/2025/final`

Current manifest snapshot:

- Players: 224
- Dataset status: `strong`
- Evidence depth: 178 high, 30 medium, 16 low
- Canonical baseline: 224 players and 846 pre-draft season-stat rows
- Disagreement buckets: 76 aligned, 21 model higher, 127 reference higher
- Source coverage: Wikipedia draft rows, draft-slot proxy, CHL, USHL, Wikipedia career rows, and curated open-stats packs
- Score posture: model and board scores retain historical reference-rank and scouting inputs;
  `team_adjusted_score` adds the dated organization-context proxy. The reference can include
  actual draft positions and is not an independent consensus or forecast benchmark.

## Business Narrative

Position the product as draft-room preparation software, not as a black-box draft oracle.

Demo line:

> This historical board connects player evidence, reference ranks, and organization context.
> It demonstrates a review workflow. Reference ranks can contain actual draft positions, so
> agreement or disagreement with them is not evidence of predictive accuracy.

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
| Michael Misa | Familiar OHL example | Board 2, reference 2; aligned. Inspect the history rows and their sources. |
| Matthew Schaefer | Defense calibration | Board 3, reference 1; aligned. Explain the retained reference/scouting inputs. |
| Cole Reschny | CHL production | Board 15, reference 18; aligned. Compare regular-season and playoff evidence. |
| Alexei Medvedev | Goalie evidence | Board 50, reference 47; aligned. Inspect goalie-specific metrics. |
| Charlie Cerrato | NCAA/USHL path | Board 53, reference 49; aligned. Inspect the separate competition rows. |
| Anton Frondell | Adult-league context | Board 10, reference 3; aligned under the 8-slot bucket threshold. |
| Max Psenicka | Defense evidence | Board 33, reference 31; aligned. Inspect adult/playoff context. |
| Alexander Zharovsky | Russian multi-league evidence | Board 36, reference 34; aligned. Inspect MHL and KHL playoff rows. |
| Eric Nilson | Nordic coverage | Board 59, reference 45; reference higher. Use for a bucket-filter example. |
| Roman Luttsev | Late-round historical difference | Board 187, reference 206; model higher. Demonstrate shortlisting, not predictive lift. |
| Vojtech Cihar | Adult Czech exposure | Board 82, reference 59; reference higher. Compare competition context. |

These values come from the reproducible package. Rebuild before presenting; verify them in
`manifest.json` rather than treating this table as a separate source of truth. The six primary
stories are all aligned; use the backup cases for a material board-reference difference.

## Talk Track By Screen

### Board

Say:

> Use the board to select evidence for review. Its reference ranks include historical outcomes,
> while evidence depth describes the quantity of available rows and leagues.

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
- `reference higher`
- `late-round target`
- `review`

## Honest Caveats

Use these proactively:

- The 2025 class is a recent-class showcase, not an outcome-validated predictive result.
- Evidence labels are part of the product: low evidence means "needs more source coverage", not "bad player".
- The strongest current coverage is CHL, USHL/NCAA samples, curated Russian/Nordic open stats, and selected Wikipedia career rows.
- Remaining data work should prioritize the 16 low-depth players by demo importance and source availability.

## Demo Success Criteria

The demo is successful if the viewer understands three things:

1. The system can create a full-class board from fragmented public sources.
2. The board is inspectable through evidence, risk, and source traceability.
3. The workflow helps scouts find and discuss disagreement cases faster.
