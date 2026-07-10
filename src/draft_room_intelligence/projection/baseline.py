"""Baseline projection heuristics.

This module is deliberately transparent. It gives the project a runnable first
loop while leaving a clear replacement point for real trained models.
"""

from __future__ import annotations

from draft_room_intelligence.domain import Projection, Prospect


LEAGUE_FACTORS = {
    "NCAA": 1.12,
    "OHL": 1.0,
    "WHL": 0.98,
    "QMJHL": 0.95,
    "USHL": 0.92,
    "SHL": 1.2,
    "Liiga": 1.15,
    "MHL": 0.82,
}

POSITION_PREMIUM = {
    "C": 0.06,
    "RHD": 0.05,
    "LHD": 0.02,
    "G": -0.04,
    "LW": 0.0,
    "RW": 0.0,
}


def project_prospect(prospect: Prospect) -> Projection:
    age_bonus = max(0.0, 18.5 - prospect.age_at_draft) * 0.055
    league_factor = LEAGUE_FACTORS.get(prospect.league, 0.9)
    production_score = min(1.0, prospect.points_per_game * league_factor / 1.25)
    size_bonus = 0.04 if prospect.height_cm >= 188 and prospect.position != "G" else 0.0
    position_bonus = POSITION_PREMIUM.get(prospect.position, 0.0)
    consensus_signal = max(0.0, (80 - prospect.consensus_rank) / 80) * 0.32

    nhl_probability = clamp(
        0.14 + production_score * 0.38 + consensus_signal + age_bonus + size_bonus + position_bonus
    )
    impact_probability = clamp(
        nhl_probability * 0.38 + production_score * 0.16 - max(0, prospect.consensus_rank - 20) * 0.003
    )
    bust_probability = clamp(1.0 - nhl_probability + max(0, prospect.consensus_rank - 45) * 0.006)
    expected_value = round(nhl_probability * 7.0 + impact_probability * 5.0 - bust_probability * 2.0, 3)
    confidence = clamp(0.45 + min(prospect.games, 60) / 180 + (0.08 if prospect.scouting_text else 0.0))

    positives: list[str] = []
    risks: list[str] = []

    if production_score >= 0.65:
        positives.append("strong age/league-adjusted production")
    if age_bonus > 0.02:
        positives.append("young for draft class")
    if position_bonus > 0.0:
        positives.append(f"positional value at {prospect.position}")
    if size_bonus > 0.0:
        positives.append("projectable NHL frame")
    if prospect.consensus_rank <= 25:
        positives.append("strong public consensus signal")

    if production_score < 0.45:
        risks.append("modest production signal")
    if prospect.consensus_rank > 40:
        risks.append("weak consensus signal")
    if prospect.height_cm < 180 and prospect.position != "G":
        risks.append("size translation risk")

    return Projection(
        player_id=prospect.player_id,
        nhl_probability=round(nhl_probability, 3),
        impact_probability=round(impact_probability, 3),
        bust_probability=round(bust_probability, 3),
        expected_value=expected_value,
        confidence=round(confidence, 3),
        positive_drivers=tuple(positives or ["balanced profile"]),
        risk_drivers=tuple(risks or ["no major baseline risk flagged"]),
    )


def project_board(prospects: list[Prospect]) -> dict[str, Projection]:
    return {prospect.player_id: project_prospect(prospect) for prospect in prospects}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))

