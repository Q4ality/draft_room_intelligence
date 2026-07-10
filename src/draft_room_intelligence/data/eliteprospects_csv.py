"""Import local Elite Prospects CSV exports into normalized project tables."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.league_standardization import (
    infer_regular_season,
    normalize_league_name,
)


PLAYER_COLUMNS = [
    "player_id",
    "name",
    "birth_date",
    "nationality",
    "position",
    "handedness",
    "height_cm",
    "weight_kg",
    "age_at_draft",
    "source",
    "source_id",
    "source_url",
]

SEASON_STAT_LINE_COLUMNS = [
    "player_id",
    "season",
    "league",
    "team",
    "games",
    "goals",
    "assists",
    "points",
    "age",
    "timing",
    "regular_season",
    "source",
    "source_id",
    "source_url",
]


@dataclass(frozen=True)
class EliteProspectsNormalizedExport:
    players: list[dict[str, str]]
    season_stat_lines: list[dict[str, str]]


@dataclass(frozen=True)
class EliteProspectsValidationReport:
    rows: int
    unique_players: int
    stat_line_rows: int
    missing_name_rows: int
    missing_stat_context_rows: int
    missing_games_rows: int
    missing_points_rows: int
    duplicate_player_ids: tuple[str, ...]

    @property
    def has_errors(self) -> bool:
        return self.rows == 0 or self.missing_name_rows > 0

    @property
    def has_warnings(self) -> bool:
        return (
            self.missing_stat_context_rows > 0
            or self.missing_games_rows > 0
            or self.missing_points_rows > 0
            or bool(self.duplicate_player_ids)
        )


def validate_eliteprospects_export(path: str | Path) -> EliteProspectsValidationReport:
    rows = read_export(path)
    player_ids: list[str] = []
    stat_line_rows = 0
    missing_name_rows = 0
    missing_stat_context_rows = 0
    missing_games_rows = 0
    missing_points_rows = 0

    for row in rows:
        name = first_text(row, "name", "Name", "Player", "player")
        source_id = first_text(row, "ep_player_id", "EP Player ID", "Eliteprospects ID", "source_id")
        player_id = first_text(row, "player_id", "Player ID", "id") or source_id or name
        if player_id:
            player_ids.append(player_id)
        if not name:
            missing_name_rows += 1

        season = first_text(row, "season", "Season")
        league = first_text(row, "league", "League")
        team = first_text(row, "team", "Team")
        has_stat_context = bool(season or league or team)
        if has_stat_context:
            stat_line_rows += 1
            if not (season and league and team):
                missing_stat_context_rows += 1
            if not first_text(row, "games", "GP", "Games"):
                missing_games_rows += 1
            if not first_text(row, "points", "TP", "PTS", "Points"):
                missing_points_rows += 1

    return EliteProspectsValidationReport(
        rows=len(rows),
        unique_players=len(set(player_ids)),
        stat_line_rows=stat_line_rows,
        missing_name_rows=missing_name_rows,
        missing_stat_context_rows=missing_stat_context_rows,
        missing_games_rows=missing_games_rows,
        missing_points_rows=missing_points_rows,
        duplicate_player_ids=tuple(sorted(duplicates(player_ids))),
    )


def format_eliteprospects_validation_report(report: EliteProspectsValidationReport) -> str:
    lines = [
        "# Elite Prospects Export Validation",
        "",
        "## Summary",
        f"- rows: {report.rows}",
        f"- unique_players: {report.unique_players}",
        f"- stat_line_rows: {report.stat_line_rows}",
        "",
        "## Errors",
        f"- missing_name_rows: {report.missing_name_rows}",
        "",
        "## Warnings",
        f"- missing_stat_context_rows: {report.missing_stat_context_rows}",
        f"- missing_games_rows: {report.missing_games_rows}",
        f"- missing_points_rows: {report.missing_points_rows}",
        f"- duplicate_player_ids: {', '.join(report.duplicate_player_ids) or 'none'}",
    ]
    return "\n".join(lines)


def normalize_eliteprospects_export(
    path: str | Path,
    *,
    draft_year: int,
    default_timing: str = "pre_draft",
) -> EliteProspectsNormalizedExport:
    rows = read_export(path)
    players_by_id: dict[str, dict[str, str]] = {}
    stat_lines: list[dict[str, str]] = []

    for row in rows:
        player_id = first_text(row, "player_id", "Player ID", "id")
        source_id = first_text(row, "ep_player_id", "EP Player ID", "Eliteprospects ID", "source_id")
        name = required_first_text(row, "name", "Name", "Player", "player")
        if not player_id:
            player_id = build_player_id(draft_year, source_id, name)
        if not source_id:
            source_id = player_id

        players_by_id.setdefault(
            player_id,
            {
                "player_id": player_id,
                "name": name,
                "birth_date": first_text(row, "birth_date", "Date of Birth", "DOB"),
                "nationality": first_text(row, "nationality", "Nation", "Country"),
                "position": normalize_position(first_text(row, "position", "Position", "Pos")),
                "handedness": first_text(row, "handedness", "Shoots", "Catches"),
                "height_cm": first_text(row, "height_cm", "Height (cm)", "Height"),
                "weight_kg": first_text(row, "weight_kg", "Weight (kg)", "Weight"),
                "age_at_draft": first_text(row, "age_at_draft", "Draft Age", "Age"),
                "source": "eliteprospects",
                "source_id": source_id,
                "source_url": first_text(row, "source_url", "URL", "Profile URL"),
            },
        )

        season = first_text(row, "season", "Season")
        league = first_text(row, "league", "League")
        team = first_text(row, "team", "Team")
        if season or league or team:
            stage = first_text(row, "season_type", "Stage", "Competition")
            stat_lines.append(
                {
                    "player_id": player_id,
                    "season": season,
                    "league": normalize_league_name(league),
                    "team": team,
                    "games": first_text(row, "games", "GP", "Games"),
                    "goals": first_text(row, "goals", "G", "Goals"),
                    "assists": first_text(row, "assists", "A", "Assists"),
                    "points": first_text(row, "points", "TP", "PTS", "Points"),
                    "age": first_text(row, "stat_age", "Season Age"),
                    "timing": first_text(row, "timing", "Timing") or default_timing,
                    "regular_season": (
                        first_text(row, "regular_season", "Regular Season")
                        or ("true" if infer_regular_season(stage, league, team) else "false")
                    ),
                    "source": "eliteprospects",
                    "source_id": source_id,
                    "source_url": first_text(row, "source_url", "URL", "Profile URL"),
                }
            )

    return EliteProspectsNormalizedExport(
        players=sorted(players_by_id.values(), key=lambda player: player["player_id"]),
        season_stat_lines=sorted(
            stat_lines,
            key=lambda line: (line["player_id"], line["season"], line["league"], line["team"]),
        ),
    )


def write_eliteprospects_normalized_tables(
    export_path: str | Path,
    output_dir: str | Path,
    *,
    draft_year: int,
    default_timing: str = "pre_draft",
) -> EliteProspectsNormalizedExport:
    normalized = normalize_eliteprospects_export(
        export_path,
        draft_year=draft_year,
        default_timing=default_timing,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_table(root / "players.csv", PLAYER_COLUMNS, normalized.players)
    write_table(root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, normalized.season_stat_lines)
    return normalized


def read_export(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_table(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def required_first_text(row: dict[str, str], *columns: str) -> str:
    value = first_text(row, *columns)
    if not value:
        joined = ", ".join(columns)
        raise ValueError(f"one of these columns is required: {joined}")
    return value


def first_text(row: dict[str, str], *columns: str) -> str:
    normalized = {normalize_header(key): value for key, value in row.items()}
    for column in columns:
        value = normalized.get(normalize_header(column), "")
        if value is not None and value.strip():
            return value.strip()
    return ""


def normalize_header(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def normalize_position(position: str) -> str:
    return position.replace("/", "").upper()


def build_player_id(draft_year: int, source_id: str, name: str) -> str:
    suffix = source_id or slugify(name)
    return f"{draft_year}-ep-{suffix}"


def slugify(value: str) -> str:
    return "-".join(
        "".join(character.lower() for character in part if character.isalnum())
        for part in value.split()
    )


def duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated
