"""Reusable feature table generation for historical prospect models."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.league_standardization import normalize_league_name
from draft_room_intelligence.domain import HistoricalProspect
from draft_room_intelligence.evaluation.baselines import (
    consensus_probability,
    draft_slot_probability,
)
from draft_room_intelligence.projection.production_adjustment import (
    build_adjusted_production_features,
    load_league_context,
    lookup_context,
)


FEATURE_COLUMNS = [
    "player_id",
    "name",
    "draft_year",
    "role_group",
    "position",
    "consensus_rank",
    "consensus_score",
    "slot_score",
    "adjusted_production_score",
    "adjusted_ppg",
    "role_rank",
    "role_percentile",
    "pre_draft_row_count",
    "pre_draft_league_count",
    "pre_draft_total_games",
    "pre_draft_total_points",
    "pre_draft_points_per_game",
    "pre_draft_regular_season_games",
    "pre_draft_playoff_games",
    "adult_game_share",
    "junior_game_share",
    "college_game_share",
    "pro_game_share",
    "average_league_weight",
    "primary_league",
    "primary_league_family",
    "primary_competition_level",
    "playoff_row_count",
    "playoff_game_share",
    "adult_league_exposure",
    "adult_league_bonus",
    "playoff_bonus",
    "height_cm",
    "weight_kg",
    "age_at_draft",
    "handedness",
    "handedness_score",
    "size_score",
    "age_score",
    "is_goalie",
    "is_defense",
    "is_forward",
    "is_nhler",
    "is_impact_player",
    "is_bust",
    "nhl_games",
    "nhl_points",
]

MODEL_FEATURE_COLUMNS = [
    "consensus_score",
    "slot_score",
    "adjusted_production_score",
    "adjusted_ppg",
    "role_percentile",
    "pre_draft_row_count",
    "pre_draft_league_count",
    "pre_draft_total_games",
    "pre_draft_total_points",
    "pre_draft_points_per_game",
    "pre_draft_regular_season_games",
    "pre_draft_playoff_games",
    "adult_game_share",
    "junior_game_share",
    "college_game_share",
    "pro_game_share",
    "average_league_weight",
    "playoff_row_count",
    "playoff_game_share",
    "adult_league_exposure",
    "adult_league_bonus",
    "playoff_bonus",
    "height_cm",
    "weight_kg",
    "age_at_draft",
    "handedness_score",
    "size_score",
    "age_score",
]


@dataclass(frozen=True)
class FeatureRow:
    values: dict[str, str]

    def to_dict(self) -> dict[str, str]:
        return dict(self.values)


def build_feature_rows(prospects: list[HistoricalProspect]) -> list[FeatureRow]:
    adjusted_features = build_adjusted_production_features(prospects)
    league_contexts = load_league_context()
    max_adjusted = max((feature.adjusted_score for feature in adjusted_features.values()), default=0.0)
    max_rank = max((prospect.consensus_rank for prospect in prospects), default=100)

    rows: list[FeatureRow] = []
    for prospect in prospects:
        stat_lines = prospect.pre_draft_stat_lines or (prospect.stat_line,)
        total_games = sum(line.games for line in stat_lines)
        total_points = sum(line.total_points for line in stat_lines)
        league_count = len({line.league for line in stat_lines})
        playoff_row_count = sum(1 for line in stat_lines if not line.regular_season)
        playoff_games = sum(line.games for line in stat_lines if not line.regular_season)
        regular_season_games = sum(line.games for line in stat_lines if line.regular_season)
        points_per_game = total_points / total_games if total_games else 0.0
        role = role_group(prospect)
        adjusted = adjusted_features.get(prospect.player_id)
        adjusted_score = (
            adjusted.adjusted_score / max_adjusted
            if adjusted is not None and max_adjusted > 0
            else 0.0
        )
        adult_exposure = 1.0 if adjusted is not None and adjusted.adult_league else 0.0
        primary_line = max(stat_lines, key=lambda line: line.games, default=prospect.stat_line)
        primary_context = lookup_context(primary_line.league, league_contexts)
        adult_games = 0
        junior_games = 0
        college_games = 0
        pro_games = 0
        weighted_games = 0.0

        for line in stat_lines:
            context = lookup_context(normalize_league_name(line.league), league_contexts)
            weighted_games += line.games * context.league_weight
            if context.adult_league:
                adult_games += line.games
            if context.competition_level == "junior":
                junior_games += line.games
            elif context.competition_level == "junior_a":
                junior_games += line.games
            elif context.league_family == "College":
                college_games += line.games
            if context.adult_league:
                pro_games += line.games

        rows.append(
            FeatureRow(
                {
                    "player_id": prospect.player_id,
                    "name": prospect.name,
                    "draft_year": str(prospect.draft_year),
                    "role_group": role,
                    "position": prospect.position,
                    "consensus_rank": str(prospect.consensus_rank),
                    "consensus_score": f"{consensus_probability(prospect, max_rank=max_rank):.6f}",
                    "slot_score": f"{draft_slot_probability(prospect):.6f}",
                    "adjusted_production_score": f"{adjusted_score:.6f}",
                    "adjusted_ppg": f"{(adjusted.adjusted_ppg if adjusted else 0.0):.6f}",
                    "role_rank": str(adjusted.role_rank if adjusted else 0),
                    "role_percentile": f"{(adjusted.role_percentile if adjusted else 0.0):.6f}",
                    "pre_draft_row_count": str(len(stat_lines)),
                    "pre_draft_league_count": str(league_count),
                    "pre_draft_total_games": str(total_games),
                    "pre_draft_total_points": str(total_points),
                    "pre_draft_points_per_game": f"{points_per_game:.6f}",
                    "pre_draft_regular_season_games": str(regular_season_games),
                    "pre_draft_playoff_games": str(playoff_games),
                    "adult_game_share": f"{(adult_games / total_games if total_games else 0.0):.6f}",
                    "junior_game_share": f"{(junior_games / total_games if total_games else 0.0):.6f}",
                    "college_game_share": f"{(college_games / total_games if total_games else 0.0):.6f}",
                    "pro_game_share": f"{(pro_games / total_games if total_games else 0.0):.6f}",
                    "average_league_weight": f"{(weighted_games / total_games if total_games else 0.0):.6f}",
                    "primary_league": normalize_league_name(primary_line.league),
                    "primary_league_family": primary_context.league_family,
                    "primary_competition_level": primary_context.competition_level,
                    "playoff_row_count": str(playoff_row_count),
                    "playoff_game_share": f"{(playoff_games / total_games if total_games else 0.0):.6f}",
                    "adult_league_exposure": f"{adult_exposure:.6f}",
                    "adult_league_bonus": f"{(adjusted.adult_league_bonus if adjusted else 0.0):.6f}",
                    "playoff_bonus": f"{(adjusted.playoff_bonus if adjusted else 0.0):.6f}",
                    "height_cm": str(prospect.height_cm),
                    "weight_kg": str(prospect.weight_kg),
                    "age_at_draft": f"{prospect.age_at_draft:.6f}",
                    "handedness": prospect.handedness,
                    "handedness_score": f"{handedness_score(prospect):.6f}",
                    "size_score": f"{size_score(prospect):.6f}",
                    "age_score": f"{age_score(prospect):.6f}",
                    "is_goalie": "1" if role == "goalie" else "0",
                    "is_defense": "1" if role == "defense" else "0",
                    "is_forward": "1" if role == "forward" else "0",
                    "is_nhler": "1" if prospect.outcome and prospect.outcome.is_nhler else "0",
                    "is_impact_player": "1" if prospect.outcome and prospect.outcome.is_impact_player else "0",
                    "is_bust": "1" if prospect.outcome and prospect.outcome.is_bust else "0",
                    "nhl_games": str(prospect.outcome.nhl_games if prospect.outcome else 0),
                    "nhl_points": str(prospect.outcome.nhl_points if prospect.outcome else 0),
                }
            )
        )
    return rows


def write_feature_table(path: str | Path, rows: list[FeatureRow]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(row.to_dict() for row in rows)


def role_group(prospect: HistoricalProspect) -> str:
    if prospect.position == "G":
        return "goalie"
    if prospect.position == "D" or prospect.position.endswith("HD"):
        return "defense"
    return "forward"


def handedness_score(prospect: HistoricalProspect) -> float:
    if prospect.position == "D" and prospect.handedness == "R":
        return 1.0
    if prospect.position == "G" and prospect.handedness:
        return 0.55
    if prospect.handedness:
        return 0.5
    return 0.35


def size_score(prospect: HistoricalProspect) -> float:
    if prospect.position == "G":
        return clamp((prospect.height_cm - 180) / 20) * 0.8 + clamp((prospect.weight_kg - 75) / 20) * 0.2
    if prospect.position == "D":
        return clamp((prospect.height_cm - 178) / 18) * 0.7 + clamp((prospect.weight_kg - 72) / 22) * 0.3
    return clamp((prospect.height_cm - 172) / 18) * 0.65 + clamp((prospect.weight_kg - 68) / 20) * 0.35


def age_score(prospect: HistoricalProspect) -> float:
    return clamp((18.9 - prospect.age_at_draft) / 1.4)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
