"""Reusable feature table generation for historical prospect models."""

from __future__ import annotations

import csv
import math
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
    "adult_games",
    "adult_sample_tier",
    "adult_evidence_weight",
    "meaningful_adult_sample",
    "adult_game_share",
    "junior_game_share",
    "college_game_share",
    "pro_game_share",
    "average_league_weight",
    "primary_league",
    "primary_league_family",
    "primary_competition_level",
    "playoff_row_count",
    "playoff_evidence_weight",
    "meaningful_playoff_sample",
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
    "goalie_games",
    "goalie_minutes",
    "goalie_shots_against",
    "goalie_saves",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_shutouts",
    "goalie_quality_score",
    "advanced_games",
    "advanced_sample_weight",
    "plus_minus_per_game",
    "shots_per_game",
    "blocks_per_game",
    "faceoff_percentage",
    "advanced_role_score",
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
    "adult_games",
    "adult_evidence_weight",
    "meaningful_adult_sample",
    "adult_game_share",
    "junior_game_share",
    "college_game_share",
    "pro_game_share",
    "average_league_weight",
    "playoff_row_count",
    "playoff_evidence_weight",
    "meaningful_playoff_sample",
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
    "goalie_games",
    "goalie_minutes",
    "goalie_shots_against",
    "goalie_saves",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_shutouts",
    "goalie_quality_score",
    "advanced_sample_weight",
    "advanced_role_score",
]

ADVANCED_STAT_SCHEMA_VERSION = 1
ADVANCED_STAT_REQUIRED_COLUMNS = {
    "player_id",
    "timing",
    "games",
    "plus_minus",
    "shots",
    "blocks",
    "faceoff_wins",
    "faceoff_losses",
}


@dataclass(frozen=True)
class FeatureRow:
    values: dict[str, str]

    def to_dict(self) -> dict[str, str]:
        return dict(self.values)


@dataclass(frozen=True)
class AdvancedStatSummary:
    games: int = 0
    plus_minus: int = 0
    shots: int = 0
    blocks: int = 0
    faceoff_wins: int = 0
    faceoff_losses: int = 0


def load_advanced_stat_summaries(data_path: str | Path) -> dict[str, AdvancedStatSummary]:
    path = Path(data_path)
    source_path = path / "advanced_stat_lines.csv" if path.is_dir() else path
    if not source_path.exists() or source_path.name != "advanced_stat_lines.csv":
        return {}

    totals: dict[str, dict[str, int]] = {}
    with source_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = ADVANCED_STAT_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"advanced_stat_lines schema v{ADVANCED_STAT_SCHEMA_VERSION} missing columns: "
                + ", ".join(sorted(missing))
            )
        for row in reader:
            if row.get("timing", "pre_draft") != "pre_draft":
                continue
            player_id = row.get("player_id", "").strip()
            if not player_id:
                continue
            total = totals.setdefault(
                player_id,
                {
                    key: 0
                    for key in (
                        "games",
                        "plus_minus",
                        "shots",
                        "blocks",
                        "faceoff_wins",
                        "faceoff_losses",
                    )
                },
            )
            for key in total:
                total[key] += parse_int(row.get(key, ""))
    return {player_id: AdvancedStatSummary(**values) for player_id, values in totals.items()}


def build_feature_rows(
    prospects: list[HistoricalProspect],
    advanced_stats: dict[str, AdvancedStatSummary] | None = None,
) -> list[FeatureRow]:
    adjusted_features = build_adjusted_production_features(prospects)
    league_contexts = load_league_context()
    max_adjusted = max(
        (feature.adjusted_score for feature in adjusted_features.values()), default=0.0
    )
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
        exposure_units = total_games
        adult_exposure_units = 0
        junior_exposure_units = 0
        college_exposure_units = 0
        pro_exposure_units = 0
        weighted_exposure_units = 0.0
        goalie_metrics = build_goalie_metrics(stat_lines)
        advanced = (advanced_stats or {}).get(prospect.player_id, AdvancedStatSummary())
        advanced_metrics = build_advanced_metrics(advanced, role)

        for line in stat_lines:
            context = lookup_context(normalize_league_name(line.league), league_contexts)
            weighted_games += line.games * context.league_weight
            exposure_weight = line.games if total_games else 1
            weighted_exposure_units += exposure_weight * context.league_weight
            if context.adult_league:
                adult_games += line.games
                adult_exposure_units += exposure_weight
            if context.competition_level == "junior":
                junior_games += line.games
                junior_exposure_units += exposure_weight
            elif context.competition_level == "junior_a":
                junior_games += line.games
                junior_exposure_units += exposure_weight
            elif context.league_family == "College":
                college_games += line.games
                college_exposure_units += exposure_weight
            if context.adult_league:
                pro_games += line.games
                pro_exposure_units += exposure_weight

        if total_games == 0:
            exposure_units = len(stat_lines)

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
                    "adult_games": str(adult_games),
                    "adult_sample_tier": adjusted.adult_sample_tier
                    if adjusted
                    else ("exposure" if adult_games > 0 else "none"),
                    "adult_evidence_weight": f"{(adjusted.adult_evidence_weight if adjusted else 0.0):.6f}",
                    "meaningful_adult_sample": "1"
                    if adjusted and adjusted.meaningful_adult_sample
                    else "0",
                    "adult_game_share": f"{share(adult_games, total_games, adult_exposure_units, exposure_units):.6f}",
                    "junior_game_share": f"{share(junior_games, total_games, junior_exposure_units, exposure_units):.6f}",
                    "college_game_share": f"{share(college_games, total_games, college_exposure_units, exposure_units):.6f}",
                    "pro_game_share": f"{share(pro_games, total_games, pro_exposure_units, exposure_units):.6f}",
                    "average_league_weight": f"{league_average(weighted_games, total_games, weighted_exposure_units, exposure_units):.6f}",
                    "primary_league": normalize_league_name(primary_line.league),
                    "primary_league_family": primary_context.league_family,
                    "primary_competition_level": primary_context.competition_level,
                    "playoff_row_count": str(playoff_row_count),
                    "playoff_evidence_weight": f"{(adjusted.playoff_evidence_weight if adjusted else 0.0):.6f}",
                    "meaningful_playoff_sample": "1"
                    if adjusted and adjusted.meaningful_playoff_sample
                    else "0",
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
                    "goalie_games": str(goalie_metrics["games"]),
                    "goalie_minutes": f"{goalie_metrics['minutes']:.2f}",
                    "goalie_shots_against": str(goalie_metrics["shots_against"]),
                    "goalie_saves": str(goalie_metrics["saves"]),
                    "goalie_save_percentage": f"{goalie_metrics['save_percentage']:.6f}",
                    "goalie_goals_against_average": f"{goalie_metrics['goals_against_average']:.6f}",
                    "goalie_shutouts": str(goalie_metrics["shutouts"]),
                    "goalie_quality_score": f"{goalie_metrics['quality_score']:.6f}",
                    "advanced_games": str(advanced.games),
                    "advanced_sample_weight": f"{advanced_metrics['sample_weight']:.6f}",
                    "plus_minus_per_game": f"{advanced_metrics['plus_minus_per_game']:.6f}",
                    "shots_per_game": f"{advanced_metrics['shots_per_game']:.6f}",
                    "blocks_per_game": f"{advanced_metrics['blocks_per_game']:.6f}",
                    "faceoff_percentage": f"{advanced_metrics['faceoff_percentage']:.6f}",
                    "advanced_role_score": f"{advanced_metrics['role_score']:.6f}",
                    "is_goalie": "1" if role == "goalie" else "0",
                    "is_defense": "1" if role == "defense" else "0",
                    "is_forward": "1" if role == "forward" else "0",
                    "is_nhler": "1" if prospect.outcome and prospect.outcome.is_nhler else "0",
                    "is_impact_player": "1"
                    if prospect.outcome and prospect.outcome.is_impact_player
                    else "0",
                    "is_bust": "1" if prospect.outcome and prospect.outcome.is_bust else "0",
                    "nhl_games": str(prospect.outcome.nhl_games if prospect.outcome else 0),
                    "nhl_points": str(prospect.outcome.nhl_points if prospect.outcome else 0),
                }
            )
        )
    return rows


def build_advanced_metrics(summary: AdvancedStatSummary, role: str) -> dict[str, float]:
    games = summary.games
    sample_weight = min(games / 20.0, 1.0) if games else 0.0
    plus_minus_per_game = summary.plus_minus / games if games else 0.0
    shots_per_game = summary.shots / games if games else 0.0
    blocks_per_game = summary.blocks / games if games else 0.0
    faceoff_attempts = summary.faceoff_wins + summary.faceoff_losses
    faceoff_percentage = summary.faceoff_wins / faceoff_attempts if faceoff_attempts else 0.0

    plus_minus_signal = logistic(plus_minus_per_game * 2.0)
    shot_signal = clamp(shots_per_game / 4.0)
    block_signal = clamp(blocks_per_game / 2.0)
    faceoff_signal = clamp((faceoff_percentage - 0.35) / 0.30) if faceoff_attempts else 0.0
    if role == "defense":
        unweighted_score = 0.35 * plus_minus_signal + 0.25 * shot_signal + 0.40 * block_signal
    elif role == "forward":
        unweighted_score = 0.20 * plus_minus_signal + 0.50 * shot_signal + 0.30 * faceoff_signal
    else:
        unweighted_score = 0.0
    return {
        "sample_weight": sample_weight,
        "plus_minus_per_game": plus_minus_per_game,
        "shots_per_game": shots_per_game,
        "blocks_per_game": blocks_per_game,
        "faceoff_percentage": faceoff_percentage,
        "role_score": unweighted_score * sample_weight,
    }


def parse_int(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def logistic(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


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
        return (
            clamp((prospect.height_cm - 180) / 20) * 0.8
            + clamp((prospect.weight_kg - 75) / 20) * 0.2
        )
    if prospect.position == "D":
        return (
            clamp((prospect.height_cm - 178) / 18) * 0.7
            + clamp((prospect.weight_kg - 72) / 22) * 0.3
        )
    return (
        clamp((prospect.height_cm - 172) / 18) * 0.65 + clamp((prospect.weight_kg - 68) / 20) * 0.35
    )


def age_score(prospect: HistoricalProspect) -> float:
    return clamp((18.9 - prospect.age_at_draft) / 1.4)


def build_goalie_metrics(stat_lines) -> dict[str, float | int]:
    goalie_lines = [
        line
        for line in stat_lines
        if line.save_percentage is not None
        or line.goals_against_average is not None
        or line.saves is not None
        or line.shots_against is not None
    ]
    games = sum(line.games for line in goalie_lines)
    minutes = sum(line.goalie_minutes or 0.0 for line in goalie_lines)
    shots_against = sum(line.shots_against or 0 for line in goalie_lines)
    saves = sum(line.saves or 0 for line in goalie_lines)
    goals_against = sum(line.goals_against or 0 for line in goalie_lines)
    shutouts = sum(line.shutouts or 0 for line in goalie_lines)
    save_percentage = (
        saves / shots_against
        if shots_against
        else weighted_average([(line.save_percentage, line.games) for line in goalie_lines])
    )
    goals_against_average = (
        goals_against * 60 / minutes
        if minutes
        else weighted_average([(line.goals_against_average, line.games) for line in goalie_lines])
    )
    quality_score = goalie_quality_score(save_percentage, goals_against_average, games)
    return {
        "games": games,
        "minutes": minutes,
        "shots_against": shots_against,
        "saves": saves,
        "save_percentage": save_percentage,
        "goals_against_average": goals_against_average,
        "shutouts": shutouts,
        "quality_score": quality_score,
    }


def weighted_average(values: list[tuple[float | None, int]]) -> float:
    numerator = 0.0
    denominator = 0
    for value, weight in values:
        if value is None:
            continue
        numerator += value * max(weight, 1)
        denominator += max(weight, 1)
    return numerator / denominator if denominator else 0.0


def goalie_quality_score(save_percentage: float, goals_against_average: float, games: int) -> float:
    if not save_percentage and not goals_against_average:
        return 0.0
    save_component = clamp((save_percentage - 0.880) / 0.050) if save_percentage else 0.0
    gaa_component = clamp((3.50 - goals_against_average) / 1.50) if goals_against_average else 0.0
    sample_component = clamp(games / 35)
    return (save_component * 0.55) + (gaa_component * 0.30) + (sample_component * 0.15)


def share(game_value: int, total_games: int, exposure_value: int, exposure_units: int) -> float:
    if total_games:
        return game_value / total_games
    return exposure_value / exposure_units if exposure_units else 0.0


def league_average(
    weighted_games: float,
    total_games: int,
    weighted_exposure_units: float,
    exposure_units: int,
) -> float:
    if total_games:
        return weighted_games / total_games
    return weighted_exposure_units / exposure_units if exposure_units else 0.0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
