"""CSV loader for normalized historical prospect rows.

The loader intentionally targets a project-owned normalized schema rather than
one raw vendor/source format. Scrapers or manual exports can map public draft
tables, ranking files, and pre-draft stat tables into this shape.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from draft_room_intelligence.domain import (
    DevelopmentStatLine,
    DraftOutcome,
    DraftSelection,
    HistoricalProspect,
    PreDraftStatLine,
    SourceRecord,
)


REQUIRED_COLUMNS = {
    "player_id",
    "name",
    "draft_year",
    "position",
    "age_at_draft",
    "height_cm",
    "weight_kg",
    "consensus_rank",
    "league",
    "team",
    "season",
    "games",
    "goals",
    "assists",
}


def load_historical_prospects_csv(path: str | Path) -> list[HistoricalProspect]:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        validate_columns(reader.fieldnames, csv_path)
        return [row_to_historical_prospect(row) for row in reader]


def row_to_historical_prospect(row: dict[str, str]) -> HistoricalProspect:
    player_id = required_text(row, "player_id")
    draft_year = required_int(row, "draft_year")
    stat_line = PreDraftStatLine(
        league=required_text(row, "league"),
        team=required_text(row, "team"),
        season=required_text(row, "season"),
        games=required_int(row, "games"),
        goals=required_int(row, "goals"),
        assists=required_int(row, "assists"),
        points=optional_int(row, "points"),
    )
    pre_draft_stat_lines = build_pre_draft_stat_lines(row, stat_line)

    return HistoricalProspect(
        player_id=player_id,
        name=required_text(row, "name"),
        draft_year=draft_year,
        position=required_text(row, "position"),
        age_at_draft=required_float(row, "age_at_draft"),
        height_cm=required_int(row, "height_cm"),
        weight_kg=required_int(row, "weight_kg"),
        consensus_rank=required_int(row, "consensus_rank"),
        stat_line=stat_line,
        handedness=optional_text(row, "handedness"),
        nationality=optional_text(row, "nationality"),
        pre_draft_stat_lines=pre_draft_stat_lines,
        selection=build_selection(row, draft_year),
        outcome=build_outcome(row, player_id),
        development_path=build_development_path(row),
        sources=build_sources(row, player_id, draft_year),
        scouting_text=optional_text(row, "scouting_text"),
    )


def validate_columns(fieldnames: Iterable[str] | None, path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"{path} does not contain a CSV header row")

    missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{path} is missing required columns: {joined}")


def build_selection(row: dict[str, str], draft_year: int) -> DraftSelection | None:
    team_id = optional_text(row, "draft_team_id")
    round_number = optional_int(row, "round_number")
    overall_pick = optional_int(row, "overall_pick")

    if not any((team_id, round_number, overall_pick)):
        return None
    if not team_id or round_number is None or overall_pick is None:
        raise ValueError("draft_team_id, round_number, and overall_pick must be provided together")

    return DraftSelection(
        draft_year=draft_year,
        team_id=team_id,
        round_number=round_number,
        overall_pick=overall_pick,
    )


def build_outcome(row: dict[str, str], player_id: str) -> DraftOutcome | None:
    nhl_games = optional_int(row, "nhl_games")
    nhl_points = optional_int(row, "nhl_points")

    if nhl_games is None and nhl_points is None:
        return None
    if nhl_games is None or nhl_points is None:
        raise ValueError("nhl_games and nhl_points must be provided together")

    return DraftOutcome(
        player_id=player_id,
        nhl_games=nhl_games,
        nhl_points=nhl_points,
        seasons_played=optional_int(row, "seasons_played") or 0,
        time_to_nhl_years=optional_float(row, "time_to_nhl_years"),
        value_proxy=optional_float(row, "value_proxy"),
    )


def build_development_path(row: dict[str, str]) -> tuple[DevelopmentStatLine, ...]:
    raw_value = optional_text(row, "development_stat_lines")
    if not raw_value:
        return ()

    payload = json.loads(raw_value)
    if not isinstance(payload, list):
        raise ValueError("development_stat_lines must be a JSON list")

    return tuple(build_development_stat_line(item) for item in payload)


def build_pre_draft_stat_lines(
    row: dict[str, str],
    default_stat_line: PreDraftStatLine,
) -> tuple[PreDraftStatLine, ...]:
    raw_value = optional_text(row, "pre_draft_stat_lines")
    if not raw_value:
        return (default_stat_line,)

    payload = json.loads(raw_value)
    if not isinstance(payload, list):
        raise ValueError("pre_draft_stat_lines must be a JSON list")

    lines = tuple(build_pre_draft_stat_line(item) for item in payload)
    return lines or (default_stat_line,)


def build_pre_draft_stat_line(item: object) -> PreDraftStatLine:
    if not isinstance(item, dict):
        raise ValueError("pre_draft_stat_lines entries must be JSON objects")

    return PreDraftStatLine(
        league=required_mapping_text(item, "league"),
        team=required_mapping_text(item, "team"),
        season=required_mapping_text(item, "season"),
        games=required_mapping_int(item, "games"),
        goals=required_mapping_int(item, "goals"),
        assists=required_mapping_int(item, "assists"),
        points=optional_mapping_int(item, "points"),
        regular_season=optional_mapping_bool(item, "regular_season", default=True),
    )


def build_development_stat_line(item: object) -> DevelopmentStatLine:
    if not isinstance(item, dict):
        raise ValueError("development_stat_lines entries must be JSON objects")

    return DevelopmentStatLine(
        season=required_mapping_text(item, "season"),
        league=required_mapping_text(item, "league"),
        team=required_mapping_text(item, "team"),
        games=required_mapping_int(item, "games"),
        goals=required_mapping_int(item, "goals"),
        assists=required_mapping_int(item, "assists"),
        points=optional_mapping_int(item, "points"),
        age=optional_mapping_float(item, "age"),
        regular_season=optional_mapping_bool(item, "regular_season", default=True),
    )


def build_sources(
    row: dict[str, str],
    player_id: str,
    draft_year: int,
) -> tuple[SourceRecord, ...]:
    source = optional_text(row, "source")
    if not source:
        return ()

    return (
        SourceRecord(
            source=source,
            source_id=optional_text(row, "source_id") or player_id,
            player_name=required_text(row, "name"),
            draft_year=draft_year,
            url=optional_text(row, "source_url"),
        ),
    )


def required_text(row: dict[str, str], column: str) -> str:
    value = optional_text(row, column)
    if not value:
        raise ValueError(f"{column} is required")
    return value


def optional_text(row: dict[str, str], column: str) -> str:
    return row.get(column, "").strip()


def required_int(row: dict[str, str], column: str) -> int:
    value = optional_int(row, column)
    if value is None:
        raise ValueError(f"{column} is required")
    return value


def optional_int(row: dict[str, str], column: str) -> int | None:
    value = optional_text(row, column)
    if not value:
        return None
    return int(value)


def required_float(row: dict[str, str], column: str) -> float:
    value = optional_float(row, column)
    if value is None:
        raise ValueError(f"{column} is required")
    return value


def optional_float(row: dict[str, str], column: str) -> float | None:
    value = optional_text(row, column)
    if not value:
        return None
    return float(value)


def required_mapping_text(mapping: dict[str, object], key: str) -> str:
    value = optional_mapping_text(mapping, key)
    if not value:
        raise ValueError(f"development_stat_lines.{key} is required")
    return value


def optional_mapping_text(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if value is None:
        return ""
    return str(value).strip()


def required_mapping_int(mapping: dict[str, object], key: str) -> int:
    value = optional_mapping_int(mapping, key)
    if value is None:
        raise ValueError(f"development_stat_lines.{key} is required")
    return value


def optional_mapping_int(mapping: dict[str, object], key: str) -> int | None:
    value = optional_mapping_text(mapping, key)
    if not value:
        return None
    return int(value)


def optional_mapping_float(mapping: dict[str, object], key: str) -> float | None:
    value = optional_mapping_text(mapping, key)
    if not value:
        return None
    return float(value)


def optional_mapping_bool(
    mapping: dict[str, object],
    key: str,
    *,
    default: bool,
) -> bool:
    value = mapping.get(key)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"development_stat_lines.{key} must be boolean-like")
