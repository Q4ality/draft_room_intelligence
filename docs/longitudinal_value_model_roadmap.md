# Longitudinal Value Model Roadmap

## Objective

Move from a draft-board assistant to a decision-support system that estimates a prospect's expected
NHL value, uncertainty, development path, and fit with a club's roster and cap window. Distinguish
a useful descriptive ranking from a prediction validated on drafts old enough to observe outcomes.

## Phase 1: Historical Outcome Spine

Build a player-season panel for draft classes 2014-2021, with one row per player at each age and
season from two years before draft through seven post-draft seasons. Keep original pre-draft
features immutable and join outcomes separately.

Primary targets:

- NHL games, time on ice, points, value proxy, and goalie starts.
- First-NHL-game probability, regular-NHL probability, and top-six/top-four/starting-goalie odds.
- Age at junior-to-pro, AHL-to-NHL, and first sustained-NHL transitions.
- Draft-pick and public-consensus baselines retained as explicit comparators.

Use temporal splits only: train on older drafts and test on later classes. Report calibration, rank
correlation, top-N hit rate, Brier score, and uncertainty coverage by role and source family.

## Phase 2: Prospect Value Model

Start with transparent role-specific models, then compare monotonic gradient boosting and a
survival model for time-to-NHL. Features should include:

- Age-relative, league-adjusted regular-season and playoff production.
- Sample-size reliability, competition tier, adult-league exposure, and multi-season trend.
- Role evidence: goalie SV%/GAA/workload, defense shot and transition proxies, forward scoring and
  play-driving proxies.
- Size, handedness, position archetype, draft-slot, and consensus signals.
- Scouting evidence as bounded structured features, never opaque free-text scores.

Return distributions, not one score: expected NHL value, p10/p50/p90, bust probability, and the
most influential evidence. Calibrate against draft slot and consensus to demonstrate incremental lift.

## Phase 3: Club Decision Model

Combine player value with a team's actual decision context:

- Contract years, AAV/cap hit, RFA/UFA status, waiver constraints, and verified clauses.
- NHL-ready roster, AHL pipeline, rights list, U23 depth, graduation risk, and role openings.
- Team window: contender, playoff bubble, retool, or rebuild, as configurable assumptions.
- Draft-pick opportunity cost: compare expected player value with scarcity-adjusted alternatives.

Show three scenarios: best available, best organizational fit, and best cap-window fit, explaining
where and why they diverge.

## Phase 4: Retrospective Calibration Lab

For every historical class, freeze information available at draft day and compare:

1. Draft slot and consensus.
2. Elite Prospects guide features and public scouting descriptors.
3. Model score and uncertainty.
4. Actual outcomes at years 3, 5, and 7.

Create mismatch archetypes rather than anecdotes: high consensus/low outcome, low consensus/high
outcome, strong junior production that did not transfer, weak box score with a strong later outcome,
and goalie, defense, or adult-league cases where forward scoring was misleading.

Require source-date provenance for every retrospective feature. A guide released after the draft or
a stat revision published later must not leak into draft-day features.

## Source Strategy

| Family | Preferred source | Use | Constraint |
| --- | --- | --- | --- |
| NHL outcomes and draft records | NHL public stats and records | Draft, regular/playoff outcomes, transactions | Cache and version responses; public data is not a full contract registry. |
| NHL tracking | NHL EDGE | Skating, shooting, puck-zone metrics after NHL arrival | Outcome/development modeling only, never pre-draft evidence. |
| Contracts and cap | PuckPedia plus club/NHL transaction verification | AAV, cap hit, term, rights, contract context | Verify clauses/restrictions and respect source licensing. |
| CHL, USHL, NCAA, Swedish, Finnish leagues | Official feeds and cached exports | Pre-draft season/playoff and goalie evidence | Preserve raw cache, source URL, collection date, parser version. |
| Russian and Central European leagues | Official feeds where stable; reviewed open-stat fallback | KHL/MHL/VHL and adult/junior context | Reconcile identity and playoff stage; require manual review where needed. |
| Elite Prospects | Licensed export or user-provided guide PDFs | Scouting profiles, tools, league history | Respect terms; extract structured fields with confidence and page provenance. |

## Delivery Sequence

1. Create the 2014-2021 longitudinal outcome panel and a leakage audit.
2. Publish a baseline retrospective report: pick, consensus, and current feature table.
3. Train role-specific calibrated models and document incremental lift.
4. Add cap/contract and roster-window scenario inputs.
5. Ship the retrospective calibration lab in the demo with class/year switching.

## Non-Negotiable Controls

- No model claim without held-out, time-based evaluation.
- No contract or rights assertion without timestamped source provenance.
- No cross-league comparison without competition and sample-size treatment.
- Keep source confidence and missingness visible in model inputs and user recommendations.
