"""Markdown report generation for prospect cards."""

from __future__ import annotations

from draft_room_intelligence.domain import (
    Projection,
    Prospect,
    ScoutingFeatures,
    TeamAdjustedRecommendation,
)


def render_player_card(
    prospect: Prospect,
    projection: Projection,
    scouting: ScoutingFeatures,
    recommendation: TeamAdjustedRecommendation,
) -> str:
    risk_tags = ", ".join(scouting.risk_tags) if scouting.risk_tags else "none flagged"
    positives = "; ".join(projection.positive_drivers)
    risks = "; ".join(projection.risk_drivers)
    evidence = "\n".join(f"- {item}" for item in scouting.evidence) or "- No scouting text."

    return f"""## {prospect.name}

| Field | Value |
| --- | --- |
| Position | {prospect.position} |
| League | {prospect.league} |
| Draft year | {prospect.draft_year} |
| Age at draft | {prospect.age_at_draft:.1f} |
| Production | {prospect.goals}-{prospect.assists}-{prospect.points} in {prospect.games} GP |
| Consensus rank | {prospect.consensus_rank} |

### Projection

- NHL probability: {projection.nhl_probability:.1%}
- Impact probability: {projection.impact_probability:.1%}
- Bust probability: {projection.bust_probability:.1%}
- Expected value: {projection.expected_value}
- Confidence: {projection.confidence:.1%}
- Positive drivers: {positives}
- Risk drivers: {risks}

### Scouting Intelligence

- Role projection: {scouting.role_projection}
- Skating score: {scouting.skating_score}
- Hockey IQ score: {scouting.hockey_iq_score}
- Compete score: {scouting.compete_score}
- Defense score: {scouting.defense_score}
- Skill score: {scouting.skill_score}
- Risk tags: {risk_tags}

Evidence:

{evidence}

### Team-Adjusted Recommendation

- Base value: {recommendation.base_value}
- Team fit bonus: {recommendation.team_fit_bonus}
- Risk penalty: {recommendation.risk_penalty}
- Adjusted value: {recommendation.adjusted_value}
- Recommendation: {recommendation.recommendation}
"""

