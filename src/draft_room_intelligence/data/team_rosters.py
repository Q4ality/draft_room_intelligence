"""Roster-depth inputs for team-view draft analysis."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROSTER_COLUMNS = [
    "team_id",
    "team_name",
    "league_level",
    "affiliate_of",
    "player_id",
    "player_name",
    "position",
    "handedness",
    "age",
    "height_cm",
    "weight_kg",
    "games",
    "goals",
    "assists",
    "points",
    "plus_minus",
    "time_on_ice_per_game",
    "goalie_minutes",
    "goalie_wins",
    "goalie_saves",
    "goalie_shots_against",
    "goalie_goals_against",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_shutouts",
    "source",
    "source_id",
    "source_url",
]

DEPTH_COLUMNS = [
    "team_id",
    "team_name",
    "league_level",
    "affiliate_of",
    "role_bucket",
    "role_type",
    "players",
    "under_25",
    "age_25_to_29",
    "age_30_plus",
    "right_shots",
    "left_shots",
    "avg_age",
    "avg_points_per_game",
    "avg_goalie_save_percentage",
    "avg_goalie_goals_against_average",
    "goalie_wins",
    "goalie_shutouts",
    "scarcity_target",
    "scarcity_score",
    "example_players",
]


@dataclass(frozen=True)
class RosterPlayer:
    team_id: str
    team_name: str
    league_level: str
    affiliate_of: str
    player_id: str
    player_name: str
    position: str
    handedness: str = ""
    age: float = 0.0
    height_cm: int = 0
    weight_kg: int = 0
    games: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int | None = None
    time_on_ice_per_game: float | None = None
    goalie_minutes: float | None = None
    goalie_wins: int = 0
    goalie_saves: int = 0
    goalie_shots_against: int = 0
    goalie_goals_against: int = 0
    goalie_save_percentage: float | None = None
    goalie_goals_against_average: float | None = None
    goalie_shutouts: int = 0
    source: str = ""
    source_id: str = ""
    source_url: str = ""

    @property
    def points_per_game(self) -> float:
        return self.points / self.games if self.games else 0.0

    @property
    def role_bucket(self) -> str:
        return role_bucket(self.position)

    @property
    def role_type(self) -> str:
        return classify_role_type(self)


@dataclass(frozen=True)
class DepthRow:
    values: dict[str, str]

    def to_dict(self) -> dict[str, str]:
        return dict(self.values)


def load_roster_csv(path: str | Path) -> list[RosterPlayer]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        return [row_to_roster_player(row) for row in csv.DictReader(file)]


def write_roster_csv(path: str | Path, players: list[RosterPlayer]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=ROSTER_COLUMNS)
        writer.writeheader()
        for player in players:
            writer.writerow(roster_player_to_row(player))


def write_depth_csv(path: str | Path, rows: list[DepthRow]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=DEPTH_COLUMNS)
        writer.writeheader()
        writer.writerows(row.to_dict() for row in rows)


def build_depth_rows(players: list[RosterPlayer]) -> list[DepthRow]:
    grouped: dict[tuple[str, str, str, str, str, str], list[RosterPlayer]] = {}
    for player in players:
        key = (
            player.team_id,
            player.team_name,
            player.league_level,
            player.affiliate_of,
            player.role_bucket,
            player.role_type,
        )
        grouped.setdefault(key, []).append(player)

    rows: list[DepthRow] = []
    for key, group in sorted(grouped.items()):
        team_id, team_name, league_level, affiliate_of, bucket, role_type_value = key
        target = scarcity_target(bucket, role_type_value, league_level)
        count = len(group)
        avg_age = average([player.age for player in group if player.age])
        avg_ppg = average([player.points_per_game for player in group if player.games])
        avg_goalie_save_percentage = weighted_average(
            [(player.goalie_save_percentage, player.games) for player in group if player.goalie_save_percentage]
        )
        avg_goalie_goals_against_average = weighted_average(
            [
                (player.goalie_goals_against_average, player.games)
                for player in group
                if player.goalie_goals_against_average
            ]
        )
        scarcity = max(0.0, (target - count) / target) if target else 0.0
        rows.append(
            DepthRow(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "league_level": league_level,
                    "affiliate_of": affiliate_of,
                    "role_bucket": bucket,
                    "role_type": role_type_value,
                    "players": str(count),
                    "under_25": str(sum(1 for player in group if 0 < player.age < 25)),
                    "age_25_to_29": str(sum(1 for player in group if 25 <= player.age < 30)),
                    "age_30_plus": str(sum(1 for player in group if player.age >= 30)),
                    "right_shots": str(sum(1 for player in group if player.handedness == "R")),
                    "left_shots": str(sum(1 for player in group if player.handedness == "L")),
                    "avg_age": f"{avg_age:.2f}",
                    "avg_points_per_game": f"{avg_ppg:.3f}",
                    "avg_goalie_save_percentage": f"{avg_goalie_save_percentage:.3f}"
                    if avg_goalie_save_percentage
                    else "",
                    "avg_goalie_goals_against_average": f"{avg_goalie_goals_against_average:.2f}"
                    if avg_goalie_goals_against_average
                    else "",
                    "goalie_wins": str(sum(player.goalie_wins for player in group) or ""),
                    "goalie_shutouts": str(sum(player.goalie_shutouts for player in group) or ""),
                    "scarcity_target": f"{target:.1f}",
                    "scarcity_score": f"{scarcity:.3f}",
                    "example_players": "; ".join(format_example_player(player) for player in group[:5]),
                }
            )
        )
    return rows


def format_depth_markdown(rows: list[DepthRow]) -> str:
    lines = [
        "# Organizational Depth Report",
        "",
        "| Team | Level | Role | Type | Players | U25 | Scarcity | Examples |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        values = row.to_dict()
        lines.append(
            "| {team_name} | {league_level} | {role_bucket} | {role_type} | {players} | "
            "{under_25} | {scarcity_score} | {example_players} |".format(**values)
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Scarcity is a roster-depth signal, not a recommendation by itself.",
            "- Role typing is intentionally conservative when advanced stats are missing.",
            "- The next layer should combine this with prospect role, timeline, and board value.",
        ]
    )
    return "\n".join(lines) + "\n"


def row_to_roster_player(row: dict[str, str]) -> RosterPlayer:
    return RosterPlayer(
        team_id=required_text(row, "team_id"),
        team_name=required_text(row, "team_name"),
        league_level=required_text(row, "league_level").upper(),
        affiliate_of=optional_text(row, "affiliate_of"),
        player_id=optional_text(row, "player_id") or optional_text(row, "source_id"),
        player_name=required_text(row, "player_name"),
        position=normalize_position(required_text(row, "position")),
        handedness=optional_text(row, "handedness").upper(),
        age=optional_float(row, "age"),
        height_cm=optional_int(row, "height_cm"),
        weight_kg=optional_int(row, "weight_kg"),
        games=optional_int(row, "games"),
        goals=optional_int(row, "goals"),
        assists=optional_int(row, "assists"),
        points=optional_int(row, "points"),
        plus_minus=optional_int_or_none(row, "plus_minus"),
        time_on_ice_per_game=optional_float_or_none(row, "time_on_ice_per_game"),
        goalie_minutes=optional_float_or_none(row, "goalie_minutes"),
        goalie_wins=optional_int(row, "goalie_wins"),
        goalie_saves=optional_int(row, "goalie_saves"),
        goalie_shots_against=optional_int(row, "goalie_shots_against"),
        goalie_goals_against=optional_int(row, "goalie_goals_against"),
        goalie_save_percentage=optional_float_or_none(row, "goalie_save_percentage"),
        goalie_goals_against_average=optional_float_or_none(row, "goalie_goals_against_average"),
        goalie_shutouts=optional_int(row, "goalie_shutouts"),
        source=optional_text(row, "source"),
        source_id=optional_text(row, "source_id"),
        source_url=optional_text(row, "source_url"),
    )


def roster_player_to_row(player: RosterPlayer) -> dict[str, str]:
    return {
        "team_id": player.team_id,
        "team_name": player.team_name,
        "league_level": player.league_level,
        "affiliate_of": player.affiliate_of,
        "player_id": player.player_id,
        "player_name": player.player_name,
        "position": player.position,
        "handedness": player.handedness,
        "age": f"{player.age:.1f}" if player.age else "",
        "height_cm": str(player.height_cm or ""),
        "weight_kg": str(player.weight_kg or ""),
        "games": str(player.games or ""),
        "goals": str(player.goals or ""),
        "assists": str(player.assists or ""),
        "points": str(player.points or ""),
        "plus_minus": "" if player.plus_minus is None else str(player.plus_minus),
        "time_on_ice_per_game": ""
        if player.time_on_ice_per_game is None
        else f"{player.time_on_ice_per_game:.2f}",
        "goalie_minutes": "" if player.goalie_minutes is None else f"{player.goalie_minutes:.2f}",
        "goalie_wins": str(player.goalie_wins or ""),
        "goalie_saves": str(player.goalie_saves or ""),
        "goalie_shots_against": str(player.goalie_shots_against or ""),
        "goalie_goals_against": str(player.goalie_goals_against or ""),
        "goalie_save_percentage": ""
        if player.goalie_save_percentage is None
        else f"{player.goalie_save_percentage:.3f}",
        "goalie_goals_against_average": ""
        if player.goalie_goals_against_average is None
        else f"{player.goalie_goals_against_average:.2f}",
        "goalie_shutouts": str(player.goalie_shutouts or ""),
        "source": player.source,
        "source_id": player.source_id,
        "source_url": player.source_url,
    }


def role_bucket(position: str) -> str:
    normalized = normalize_position(position)
    if normalized == "G":
        return "goalie"
    if normalized.endswith("D") or normalized == "D":
        return "defense"
    if normalized == "C":
        return "center"
    return "wing"


def classify_role_type(player: RosterPlayer) -> str:
    bucket = role_bucket(player.position)
    if bucket == "goalie":
        if player.games >= 35:
            return "starter_goalie"
        if player.games >= 15:
            return "tandem_goalie"
        return "depth_goalie"
    if bucket == "defense":
        if player.points_per_game >= 0.45:
            return "puck_moving_defense"
        if player.plus_minus is not None and player.plus_minus >= 0:
            return "two_way_defense"
        return "defense_depth"
    if bucket == "center":
        if player.points_per_game >= 0.65:
            return "scoring_center"
        if player.plus_minus is not None and player.plus_minus >= 0:
            return "two_way_center"
        return "center_depth"
    if player.points_per_game >= 0.60:
        return "scoring_wing"
    if player.plus_minus is not None and player.plus_minus >= 0:
        return "two_way_wing"
    return "wing_depth"


def scarcity_target(bucket: str, role_type_value: str, league_level: str) -> float:
    level_multiplier = 1.0 if league_level == "NHL" else 0.75
    if role_type_value in {"two_way_defense", "puck_moving_defense"}:
        return 2.0 * level_multiplier
    if role_type_value in {"scoring_center", "two_way_center"}:
        return 2.0 * level_multiplier
    if role_type_value in {"scoring_wing", "two_way_wing"}:
        return 4.0 * level_multiplier
    if bucket == "defense":
        return 6.0 * level_multiplier
    if bucket == "center":
        return 4.0 * level_multiplier
    if bucket == "wing":
        return 8.0 * level_multiplier
    if bucket == "goalie":
        return 2.0 * level_multiplier
    return 1.0


def normalize_position(value: str) -> str:
    normalized = value.strip().upper()
    if normalized in {"LD", "RD"}:
        return "D"
    if normalized in {"L", "LW"}:
        return "LW"
    if normalized in {"R", "RW"}:
        return "RW"
    return normalized


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def weighted_average(values: list[tuple[float | None, int]]) -> float:
    weighted_values = [(float(value), weight) for value, weight in values if value is not None and weight > 0]
    weight_sum = sum(weight for _, weight in weighted_values)
    if not weight_sum:
        return average([float(value) for value, _ in weighted_values])
    return sum(value * weight for value, weight in weighted_values) / weight_sum


def format_example_player(player: RosterPlayer) -> str:
    if player.role_bucket != "goalie":
        return player.player_name
    parts = []
    if player.goalie_wins:
        parts.append(f"{player.goalie_wins}W")
    if player.goalie_save_percentage is not None:
        parts.append(f"{player.goalie_save_percentage:.3f} SV%")
    if player.goalie_goals_against_average is not None:
        parts.append(f"{player.goalie_goals_against_average:.2f} GAA")
    if player.goalie_shutouts:
        parts.append(f"{player.goalie_shutouts} SO")
    return f"{player.player_name} ({', '.join(parts)})" if parts else player.player_name


def required_text(row: dict[str, str], key: str) -> str:
    value = optional_text(row, key)
    if not value:
        raise ValueError(f"missing required roster column: {key}")
    return value


def optional_text(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def optional_int(row: dict[str, str], key: str) -> int:
    value = optional_text(row, key)
    return int(float(value)) if value else 0


def optional_int_or_none(row: dict[str, str], key: str) -> int | None:
    value = optional_text(row, key)
    return int(float(value)) if value else None


def optional_float(row: dict[str, str], key: str) -> float:
    value = optional_text(row, key)
    return float(value) if value else 0.0


def optional_float_or_none(row: dict[str, str], key: str) -> float | None:
    value = optional_text(row, key)
    return float(value) if value else None
