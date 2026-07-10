"""Load historical prospects from normalized CSV tables."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from draft_room_intelligence.domain import (
    DevelopmentStatLine,
    DraftOutcome,
    DraftSelection,
    HistoricalProspect,
    PreDraftStatLine,
    SourceRecord,
)


def load_normalized_historical_prospects(directory: str | Path) -> list[HistoricalProspect]:
    root = Path(directory)
    players = index_by_player_id(read_table(root / "players.csv"))
    selections = index_by_player_id(read_table(root / "draft_selections.csv"))
    outcomes = index_by_player_id(read_table(root / "nhl_outcomes.csv"))
    rankings = group_by_player_id(read_optional_table(root / "rankings.csv"))
    stat_lines = group_by_player_id(read_optional_table(root / "season_stat_lines.csv"))

    prospects: list[HistoricalProspect] = []
    for player_id, player in players.items():
        selection = selections.get(player_id)
        if selection is None:
            raise ValueError(f"missing draft selection for player_id={player_id}")

        prospects.append(
            build_historical_prospect(
                player=player,
                selection_row=selection,
                outcome_row=outcomes.get(player_id),
                ranking_rows=rankings[player_id],
                stat_line_rows=stat_lines[player_id],
            )
        )

    return sorted(prospects, key=lambda prospect: prospect.draft_slot or 9999)


def build_historical_prospect(
    *,
    player: dict[str, str],
    selection_row: dict[str, str],
    outcome_row: dict[str, str] | None,
    ranking_rows: list[dict[str, str]],
    stat_line_rows: list[dict[str, str]],
) -> HistoricalProspect:
    player_id = required_text(player, "player_id")
    draft_year = required_int(selection_row, "draft_year")
    pre_draft_rows = [row for row in stat_line_rows if optional_text(row, "timing") == "pre_draft"]
    pre_draft_line = choose_pre_draft_stat_line(selection_row, stat_line_rows)
    development_path = tuple(
        build_development_stat_line(row)
        for row in stat_line_rows
        if optional_text(row, "timing") != "pre_draft"
    )

    return HistoricalProspect(
        player_id=player_id,
        name=required_text(player, "name"),
        draft_year=draft_year,
        position=required_text(player, "position"),
        age_at_draft=optional_float(player, "age_at_draft") or 18.0,
        height_cm=optional_int(player, "height_cm") or 0,
        weight_kg=optional_int(player, "weight_kg") or 0,
        consensus_rank=choose_consensus_rank(selection_row, ranking_rows),
        stat_line=pre_draft_line,
        handedness=optional_text(player, "handedness"),
        birth_date=optional_date(player, "birth_date"),
        nationality=optional_text(player, "nationality"),
        pre_draft_stat_lines=tuple(build_pre_draft_stat_line(row) for row in pre_draft_rows)
        or (pre_draft_line,),
        selection=DraftSelection(
            draft_year=draft_year,
            team_id=required_text(selection_row, "team_id"),
            round_number=required_int(selection_row, "round_number"),
            overall_pick=required_int(selection_row, "overall_pick"),
        ),
        outcome=build_outcome(outcome_row, player_id),
        development_path=development_path,
        sources=build_sources(player, selection_row, outcome_row, ranking_rows, stat_line_rows),
    )


def choose_pre_draft_stat_line(
    selection_row: dict[str, str],
    stat_line_rows: list[dict[str, str]],
) -> PreDraftStatLine:
    pre_draft_rows = [row for row in stat_line_rows if optional_text(row, "timing") == "pre_draft"]
    if pre_draft_rows:
        return build_pre_draft_stat_line(pre_draft_rows[0])

    return PreDraftStatLine(
        league=required_text(selection_row, "drafted_from_league"),
        team=required_text(selection_row, "drafted_from_team"),
        season=f"{required_int(selection_row, 'draft_year') - 1}-{str(required_int(selection_row, 'draft_year'))[-2:]}",
        games=0,
        goals=0,
        assists=0,
        points=0,
    )


def build_pre_draft_stat_line(row: dict[str, str]) -> PreDraftStatLine:
    return PreDraftStatLine(
        league=required_text(row, "league"),
        team=required_text(row, "team"),
        season=required_text(row, "season"),
        games=optional_int(row, "games") or 0,
        goals=optional_int(row, "goals") or 0,
        assists=optional_int(row, "assists") or 0,
        points=optional_int(row, "points"),
        regular_season=optional_bool(row, "regular_season", default=True),
    )


def choose_consensus_rank(
    selection_row: dict[str, str],
    ranking_rows: list[dict[str, str]],
) -> int:
    consensus_rows = [row for row in ranking_rows if optional_text(row, "source") == "consensus"]
    if consensus_rows:
        return required_int(consensus_rows[0], "rank")
    if ranking_rows:
        return min(required_int(row, "rank") for row in ranking_rows)
    return required_int(selection_row, "overall_pick")


def build_development_stat_line(row: dict[str, str]) -> DevelopmentStatLine:
    return DevelopmentStatLine(
        season=required_text(row, "season"),
        league=required_text(row, "league"),
        team=required_text(row, "team"),
        games=optional_int(row, "games") or 0,
        goals=optional_int(row, "goals") or 0,
        assists=optional_int(row, "assists") or 0,
        points=optional_int(row, "points"),
        age=optional_float(row, "age"),
        regular_season=optional_bool(row, "regular_season", default=True),
    )


def build_outcome(row: dict[str, str] | None, player_id: str) -> DraftOutcome | None:
    if row is None:
        return None
    return DraftOutcome(
        player_id=player_id,
        nhl_games=optional_int(row, "nhl_games") or 0,
        nhl_points=optional_int(row, "nhl_points") or 0,
        seasons_played=optional_int(row, "seasons_played") or 0,
        value_proxy=optional_float(row, "value_proxy"),
    )


def build_sources(
    player: dict[str, str],
    selection_row: dict[str, str],
    outcome_row: dict[str, str] | None,
    ranking_rows: list[dict[str, str]],
    stat_line_rows: list[dict[str, str]],
) -> tuple[SourceRecord, ...]:
    source_rows = [player, selection_row, *(ranking_rows or []), *(stat_line_rows or [])]
    if outcome_row is not None:
        source_rows.append(outcome_row)

    records: list[SourceRecord] = []
    seen: set[tuple[str, str]] = set()
    for row in source_rows:
        source = optional_text(row, "source")
        if not source:
            continue
        source_id = optional_text(row, "source_id") or required_text(player, "player_id")
        key = (source, source_id)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            SourceRecord(
                source=source,
                source_id=source_id,
                player_name=required_text(player, "name"),
                draft_year=required_int(selection_row, "draft_year"),
                url=optional_text(row, "source_url"),
            )
        )
    return tuple(records)


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"missing required table: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def read_optional_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_table(path)


def index_by_player_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        player_id = required_text(row, "player_id")
        if player_id in indexed:
            raise ValueError(f"duplicate player_id={player_id}")
        indexed[player_id] = row
    return indexed


def group_by_player_id(rows: list[dict[str, str]]) -> defaultdict[str, list[dict[str, str]]]:
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[required_text(row, "player_id")].append(row)
    return grouped


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


def optional_float(row: dict[str, str], column: str) -> float | None:
    value = optional_text(row, column)
    if not value:
        return None
    return float(value)


def optional_bool(row: dict[str, str], column: str, *, default: bool) -> bool:
    value = optional_text(row, column).lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{column} must be boolean-like")


def optional_date(row: dict[str, str], column: str) -> date | None:
    value = optional_text(row, column)
    if not value:
        return None
    return date.fromisoformat(value)
