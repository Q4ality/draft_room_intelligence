"""League- and role-adjusted production features."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.league_standardization import normalize_league_name
from draft_room_intelligence.domain import HistoricalProspect


DEFAULT_LEAGUE_CONTEXT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "reference" / "league_context.csv"
)


@dataclass(frozen=True)
class LeagueContext:
    league: str
    league_family: str
    competition_level: str
    adult_league: bool
    league_weight: float
    playoff_weight: float


@dataclass(frozen=True)
class AdjustedProduction:
    player_id: str
    role_group: str
    league: str
    season: str
    games: int
    points: int
    points_per_game: float
    league_weight: float
    adult_league: bool
    adjusted_ppg: float
    role_rank: int
    role_count: int
    role_percentile: float
    is_top_5_role: bool
    adult_league_bonus: float
    playoff_bonus: float
    role_bonus: float
    adjusted_score: float


def load_league_context(path: str | Path = DEFAULT_LEAGUE_CONTEXT_PATH) -> dict[str, LeagueContext]:
    contexts: dict[str, LeagueContext] = {}
    with Path(path).open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            contexts[row["league"]] = LeagueContext(
                league=row["league"],
                league_family=row["league_family"],
                competition_level=row["competition_level"],
                adult_league=parse_bool(row["adult_league"]),
                league_weight=float(row["league_weight"]),
                playoff_weight=float(row["playoff_weight"]),
            )
    return contexts


def build_adjusted_production_features(
    prospects: list[HistoricalProspect],
    *,
    league_contexts: dict[str, LeagueContext] | None = None,
) -> dict[str, AdjustedProduction]:
    contexts = league_contexts or load_league_context()
    preliminary = [
        build_preliminary_feature(prospect, contexts)
        for prospect in prospects
        if prospect.pre_draft_stat_lines and role_group(prospect.position) != "goalie"
    ]

    grouped: dict[tuple[str, str, str], list[AdjustedProduction]] = {}
    for feature in preliminary:
        grouped.setdefault((feature.season, feature.league, feature.role_group), []).append(feature)

    adjusted: dict[str, AdjustedProduction] = {}
    for group in grouped.values():
        ranked = sorted(group, key=lambda item: item.adjusted_ppg, reverse=True)
        total = len(ranked)
        for index, feature in enumerate(ranked, start=1):
            percentile = 1.0 if total == 1 else (total - index) / (total - 1)
            is_top_5 = index <= 5
            role_bonus = 0.08 if is_top_5 else 0.04 if percentile >= 0.9 else 0.0
            adjusted_score = (
                feature.adjusted_ppg
                + feature.adult_league_bonus
                + feature.playoff_bonus
                + role_bonus
            )
            adjusted[feature.player_id] = AdjustedProduction(
                player_id=feature.player_id,
                role_group=feature.role_group,
                league=feature.league,
                season=feature.season,
                games=feature.games,
                points=feature.points,
                points_per_game=feature.points_per_game,
                league_weight=feature.league_weight,
                adult_league=feature.adult_league,
                adjusted_ppg=round(feature.adjusted_ppg, 3),
                role_rank=index,
                role_count=total,
                role_percentile=round(percentile, 3),
                is_top_5_role=is_top_5,
                adult_league_bonus=feature.adult_league_bonus,
                playoff_bonus=feature.playoff_bonus,
                role_bonus=role_bonus,
                adjusted_score=round(adjusted_score, 3),
            )
    return adjusted


def build_preliminary_feature(
    prospect: HistoricalProspect,
    contexts: dict[str, LeagueContext],
) -> AdjustedProduction:
    stat_lines = prospect.pre_draft_stat_lines or (prospect.stat_line,)
    total_games = sum(max(stat_line.games, 0) for stat_line in stat_lines)
    primary_line = max(stat_lines, key=lambda stat_line: stat_line.games)
    weighted_ppg = 0.0
    adult_games = 0
    playoff_games = 0

    for stat_line in stat_lines:
        context = lookup_context(stat_line.league, contexts)
        season_weight = context.playoff_weight if not stat_line.regular_season else 1.0
        weighted_ppg += stat_line.points_per_game * stat_line.games * context.league_weight * season_weight
        if context.adult_league:
            adult_games += stat_line.games
        if not stat_line.regular_season:
            playoff_games += stat_line.games

    adjusted_ppg = weighted_ppg / total_games if total_games else 0.0
    adult_bonus = 0.06 if adult_games >= 15 else 0.03 if adult_games >= 5 else 0.0
    playoff_bonus = min(playoff_games, 20) * 0.004

    return AdjustedProduction(
        player_id=prospect.player_id,
        role_group=role_group(prospect.position),
        league=primary_line.league,
        season=primary_line.season,
        games=total_games,
        points=sum(stat_line.total_points for stat_line in stat_lines),
        points_per_game=round(
            (
                sum(stat_line.total_points for stat_line in stat_lines) / total_games
                if total_games
                else 0.0
            ),
            3,
        ),
        league_weight=round(
            sum(
                lookup_context(stat_line.league, contexts).league_weight * stat_line.games
                for stat_line in stat_lines
            )
            / total_games,
            3,
        )
        if total_games
        else 0.0,
        adult_league=adult_games > 0,
        adjusted_ppg=adjusted_ppg,
        role_rank=0,
        role_count=0,
        role_percentile=0.0,
        is_top_5_role=False,
        adult_league_bonus=adult_bonus,
        playoff_bonus=playoff_bonus,
        role_bonus=0.0,
        adjusted_score=adjusted_ppg + adult_bonus + playoff_bonus,
    )


def role_group(position: str) -> str:
    if position == "G":
        return "goalie"
    if position == "D" or position.endswith("HD"):
        return "defense"
    return "forward"


def fallback_context(league: str) -> LeagueContext:
    return LeagueContext(
        league=league,
        league_family="Unknown",
        competition_level="unknown",
        adult_league=False,
        league_weight=0.70,
        playoff_weight=1.0,
    )


def lookup_context(league: str, contexts: dict[str, LeagueContext]) -> LeagueContext:
    canonical = normalize_league_name(league)
    return contexts.get(canonical, contexts.get("Unknown", fallback_context(canonical)))


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}
