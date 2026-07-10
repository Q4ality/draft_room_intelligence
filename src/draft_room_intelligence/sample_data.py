"""Tiny sample dataset for smoke-testing the PoC flow."""

from __future__ import annotations

from draft_room_intelligence.domain import Prospect, TeamContext


def sample_prospects() -> list[Prospect]:
    return [
        Prospect(
            player_id="p001",
            name="Ilya Morozov",
            draft_year=2026,
            position="C",
            league="NCAA",
            age_at_draft=17.8,
            height_cm=191,
            weight_kg=93,
            games=36,
            goals=8,
            assists=12,
            consensus_rank=24,
            scouting_text=(
                "Big two-way center with strong defensive habits, good puck protection, "
                "high compete, and mature reads. Needs more first-step burst and faceoff polish. "
                "Projects as a middle-six matchup center."
            ),
        ),
        Prospect(
            player_id="p002",
            name="Nikita Valeev",
            draft_year=2026,
            position="LW",
            league="USHL",
            age_at_draft=18.1,
            height_cm=178,
            weight_kg=78,
            games=52,
            goals=29,
            assists=31,
            consensus_rank=18,
            scouting_text=(
                "Dynamic skilled winger with high-end hands, deceptive release, and power-play "
                "upside. Scouts note perimeter habits and inconsistent defensive engagement."
            ),
        ),
        Prospect(
            player_id="p003",
            name="Evan Hart",
            draft_year=2026,
            position="RHD",
            league="OHL",
            age_at_draft=18.4,
            height_cm=188,
            weight_kg=88,
            games=64,
            goals=9,
            assists=34,
            consensus_rank=31,
            scouting_text=(
                "Right-shot defenseman with strong transition reads, calm puck movement, "
                "and reliable defensive detail. Not a high-end offensive creator."
            ),
        ),
    ]


def sample_team_context() -> TeamContext:
    return TeamContext(
        team_id="BUF",
        name="Buffalo",
        competitive_timeline="retool",
        risk_appetite=0.45,
        position_needs={"C": 0.9, "RHD": 0.75, "LW": 0.25, "RW": 0.35, "LHD": 0.2, "G": 0.4},
        archetype_needs={"two_way": 0.8, "skilled": 0.35, "defensive": 0.65, "size": 0.55},
    )

