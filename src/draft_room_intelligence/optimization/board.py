"""Team-adjusted draft board scoring."""

from __future__ import annotations

from draft_room_intelligence.domain import (
    Projection,
    Prospect,
    ScoutingFeatures,
    TeamAdjustedRecommendation,
    TeamContext,
)


def adjust_for_team(
    prospect: Prospect,
    projection: Projection,
    scouting: ScoutingFeatures,
    team: TeamContext,
) -> TeamAdjustedRecommendation:
    position_need = team.position_needs.get(prospect.position, 0.0)
    archetype_fit = infer_archetype_fit(prospect, scouting, team)
    team_fit_bonus = round(position_need * 0.75 + archetype_fit * 0.55, 3)

    risk_penalty = round((projection.bust_probability * (1.0 - team.risk_appetite)) * 1.25, 3)
    adjusted_value = round(projection.expected_value + team_fit_bonus - risk_penalty, 3)

    return TeamAdjustedRecommendation(
        player_id=prospect.player_id,
        team_id=team.team_id,
        base_value=projection.expected_value,
        team_fit_bonus=team_fit_bonus,
        risk_penalty=risk_penalty,
        adjusted_value=adjusted_value,
        recommendation=recommendation_label(adjusted_value, projection.expected_value),
    )


def rank_board(
    prospects: list[Prospect],
    projections: dict[str, Projection],
    scouting_features: dict[str, ScoutingFeatures],
    team: TeamContext,
) -> list[TeamAdjustedRecommendation]:
    recommendations = [
        adjust_for_team(
            prospect=prospect,
            projection=projections[prospect.player_id],
            scouting=scouting_features[prospect.player_id],
            team=team,
        )
        for prospect in prospects
    ]
    return sorted(recommendations, key=lambda item: item.adjusted_value, reverse=True)


def infer_archetype_fit(
    prospect: Prospect, scouting: ScoutingFeatures, team: TeamContext
) -> float:
    fit = 0.0
    if scouting.defense_score >= 0.65 or prospect.position == "C":
        fit += team.archetype_needs.get("two_way", 0.0) * 0.45
    if scouting.skill_score >= 0.65:
        fit += team.archetype_needs.get("skilled", 0.0) * 0.35
    if prospect.height_cm >= 188:
        fit += team.archetype_needs.get("size", 0.0) * 0.25
    if scouting.defense_score >= 0.7:
        fit += team.archetype_needs.get("defensive", 0.0) * 0.25
    return min(1.0, fit)


def recommendation_label(adjusted_value: float, base_value: float) -> str:
    delta = adjusted_value - base_value
    if delta >= 0.7:
        return "target above generic board"
    if delta <= -0.5:
        return "pass unless clear value"
    return "draft-range candidate"

