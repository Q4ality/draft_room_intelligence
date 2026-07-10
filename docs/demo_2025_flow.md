# 2025 Demo Flow

## Goal

Show a credible business demo of an explainable draft-room workflow for a single recent class.

Recommended showcase class: `2025 NHL Draft`

Core product promise:

- normalize fragmented pre-draft player histories across leagues,
- produce an explainable board,
- surface disagreement with consensus,
- help a draft room focus discussion on the right players.

## Audience

- amateur scouting director
- assistant GM / analytics lead
- owner or investor evaluating product value

## Demo Narrative

Use the product as a board-meeting prep tool, not as a black-box scouting replacement.

Demo line:

> "In a few minutes, we can load the 2025 class, identify where normalized evidence and public consensus disagree, inspect why, and export a shortlist for deeper discussion."

## Screen 1: Board

Purpose:

- provide a usable ranked board for the full class
- make disagreement and evidence depth visible

Layout:

- top bar
  - draft class selector
  - dataset status badge
  - export action
- left filter rail
  - position
  - league family
  - competition level
  - handedness
  - adult exposure
  - playoff exposure
  - disagreement bucket
- main board table

Required columns:

- board rank
- player name
- position
- primary league
- consensus rank
- board score
- model score
- adjusted production
- adult exposure
- playoff exposure
- evidence depth
- disagreement badge

Useful badges:

- `Model Higher`
- `Consensus Higher`
- `Adult-League`
- `Multi-League`
- `Low Evidence`

## Screen 2: Player Detail

Purpose:

- make the ranking inspectable and explainable

Sections:

1. Player header
   - name
   - position
   - nationality
   - age
   - height / weight
   - handedness
   - consensus rank
   - board rank
   - shortlist action

2. Evidence summary
   - adjusted production
   - role rank in league
   - average league weight
   - adult game share
   - playoff game share
   - primary league family
   - evidence depth

3. Why high
   - short rule-generated bullets from current features

4. Risk / uncertainty
   - thin evidence
   - mostly junior profile
   - no adult exposure
   - weak playoff coverage
   - large consensus disagreement

5. Pre-draft history table
   - season
   - league
   - team
   - games
   - goals
   - assists
   - points
   - regular season / playoff
   - source

6. Source trace
   - HockeyDB
   - Elite Prospects
   - coverage notes

## Screen 3: Compare

Purpose:

- support real draft-room debate between similar players

Mode:

- 2-player or 3-player comparison

Rows:

- consensus rank
- board score
- adjusted production
- role percentile
- primary league
- average league weight
- adult game share
- junior game share
- college game share
- playoff game share
- age
- size
- handedness
- evidence depth

Add one explanation row:

- `Why this player over the others`

## Interaction Layer: Shortlist

Purpose:

- make the demo feel like workflow software, not a static report

Minimum actions:

- shortlist toggle
- tags: `review`, `model favorite`, `consensus favorite`, `late-round target`
- short note field
- export shortlist CSV

## Recommended 7-10 Minute Demo Script

1. Open the 2025 board
2. Filter to a real decision slice, such as forwards or defenders
3. Sort by disagreement between model and consensus
4. Open one player detail for a model-favored player
5. Open one player detail for a consensus-favored player
6. Compare them side by side
7. Add one or both to shortlist
8. Export shortlist and close on business value

## Business Value To Emphasize

- faster cross-league prep
- more consistent board construction
- structured disagreement review
- explainable evidence, not black-box ranking

## Demo Readiness Requirements

### Must Have

- one curated 2025 draft dataset
- board-ready export
- player detail export
- rule-generated explanation bullets
- clean board / detail / compare views

### Nice To Have

- shortlist export
- evidence gap flags
- featured players with hand-checked rows

## Recommended Build Order

1. lock the 2025 showcase dataset
2. create a board-ready data export
3. create a player-detail data export
4. build board screen
5. build player detail
6. build compare and shortlist

## Current Backend Reuse

The current repo already provides:

- draft-year ETL
- league normalization
- multi-row pre-draft stat support
- feature table generation
- role-specific model evaluation
- source traceability in normalized tables

The demo should use those instead of inventing a separate data path.
