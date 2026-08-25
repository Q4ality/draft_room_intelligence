# Longitudinal Value Model Implementation Plan

This is the delivery plan for the strategy in
`docs/longitudinal_value_model_roadmap.md`. Each milestone is deliberately
small enough to validate before the next one changes ranking or team-fit
decisions.

## Milestone 0 вЂ” Outcome-label safety and contracts

**Goal:** make it impossible to present a career-total or future outcome as a
three-, five-, or seven-year retrospective label.

1. Define a canonical outcome-label CSV with player identity, draft year,
   horizon, outcome cutoff, NHL skater/goalie outcomes, value proxy, and
   source provenance.
2. Add a deterministic audit that rejects duplicate labels, observations dated
   after the declared evaluation cutoff, and outcomes extending past their
   declared horizon.
3. Report maturity by class and horizon; expose only explicitly eligible labels
   to held-out value-model scoring.
4. Stage only reviewed, cached outcome exports for the 2014-2021 classes.

**Acceptance:** the audit is green for every input used in retrospective
validation; all model labels are time-bounded and traceable.

## Milestone 1 вЂ” Historical outcome spine

1. Build a 2014-2021 player-level panel from normalized draft classes plus
   audited outcome labels.
2. Preserve pre-draft features separately from post-draft development and
   outcome data.
3. Add outcome availability, evidence depth, and source-family coverage to
   each panel row.
4. Publish class/horizon coverage reports before fitting a model.

**Acceptance:** the panel can be rebuilt offline from cached inputs and has
clear inclusion/exclusion reasons for every player.

## Milestone 2 вЂ” Baseline player-value estimation

1. Establish pick-slot and consensus baselines for NHL regular, impact, and
   value-proxy outcomes at 3/5/7 years.
2. Add transparent role-specific feature baselines using only draft-day
   evidence.
3. Use temporal train/test splits and report calibration, Brier score,
   rank correlation, and top-N lift by role and source coverage.
4. Return p10/p50/p90 value and confidence, not one opaque score.

**Acceptance:** any claim of incremental lift is based on held-out classes
and clearly compared with consensus.

## Milestone 3 вЂ” Player Г— team decision value

1. Version dated roster, rights, and contract snapshots.
2. Decompose pair value into standalone player value, organizational scarcity,
   opportunity, cap-window fit, and uncertainty.
3. Show best-available, best-fit, and best-cap-window scenarios with a
   component waterfall and counterfactual alternatives.
4. Backtest decisions using only information that existed on the draft date.

**Acceptance:** a team-specific recommendation is explainable, stable under
reasonable scenarios, and never changes the standalone player estimate.

## Current implementation

- [x] 0.1 Canonical outcome-label contract and audit command.
- [x] 0.2 Outcome-export coverage and staging-readiness report.
- [ ] 0.3 Reviewed 2014-2021 cached outcome exports.
- [x] 1.0 Historical pre-draft feature-coverage audit. The 2014-2021 snapshots
  currently contain only `draft_slot_proxy` rankings and no normalized pre-draft
  production or advanced-stat rows; these must not be treated as consensus or
  production features.
- [ ] 1.1 Longitudinal panel builder and coverage report.
- [x] 2.1 Time-split pick-slot and role baseline report (5-year regular-NHL
  and impact-player outcomes; train through 2018, hold out 2019-2021).
- [ ] 2.2 Consensus and production-feature baseline after historic pre-draft
  feature enrichment; report its held-out lift against the slot-and-role
  comparator.
- [ ] 3.1 Dated team-context contract and scenario inputs.
