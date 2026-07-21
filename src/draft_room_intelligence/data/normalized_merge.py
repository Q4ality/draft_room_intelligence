"""Merge source-specific normalized tables into a base draft-year dataset."""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from draft_room_intelligence.data.eliteprospects_csv import ADVANCED_STAT_LINE_COLUMNS

PASSTHROUGH_TABLES = ["draft_selections.csv", "rankings.csv", "nhl_outcomes.csv"]
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
    "goalie_minutes",
    "shots_against",
    "saves",
    "goals_against",
    "save_percentage",
    "goals_against_average",
    "wins",
    "losses",
    "ties",
    "shutouts",
]

MATCH_MAP_TEMPLATE_COLUMNS = [
    "source_player_id",
    "source_name",
    "base_player_id",
    "suggested_base_player_id",
    "suggested_base_name",
    "suggested_score",
    "candidate_2_base_player_id",
    "candidate_2_name",
    "candidate_2_score",
    "candidate_3_base_player_id",
    "candidate_3_name",
    "candidate_3_score",
    "note",
]


@dataclass(frozen=True)
class NormalizedMergeSummary:
    base_players: int
    source_players: int
    matched_players: int
    manual_matches: int
    name_matches: int
    unmatched_source_players: int
    source_stat_lines: int
    output_stat_lines: int


def merge_normalized_source_tables(
    base_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    *,
    source_name: str,
    replace_timing: str = "pre_draft",
    match_map_path: str | Path | None = None,
) -> NormalizedMergeSummary:
    base_root = Path(base_dir)
    source_root = Path(source_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    base_players = read_table(base_root / "players.csv")
    source_players = read_table(source_root / "players.csv")
    base_stat_lines = read_optional_table(base_root / "season_stat_lines.csv")
    source_stat_lines = read_optional_table(source_root / "season_stat_lines.csv")
    base_advanced_lines = read_optional_table(base_root / "advanced_stat_lines.csv")
    source_advanced_lines = read_optional_table(source_root / "advanced_stat_lines.csv")

    match_map = read_match_map(match_map_path)
    base_by_id = {row["player_id"]: row for row in base_players}
    base_by_name = {name_key(row["name"]): row for row in base_players}
    source_player_id_to_base_id: dict[str, str] = {}
    unmatched_source_players: list[dict[str, str]] = []
    manual_matches = 0
    name_matches = 0

    for source_player in source_players:
        mapped_base_id = match_map.get(source_player["player_id"])
        if mapped_base_id:
            if mapped_base_id not in base_by_id:
                raise ValueError(
                    f"match map references unknown base_player_id={mapped_base_id}"
                )
            source_player_id_to_base_id[source_player["player_id"]] = mapped_base_id
            manual_matches += 1
            continue

        base_player = base_by_name.get(name_key(source_player["name"]))
        if base_player is None:
            unmatched_source_players.append(source_player)
            continue
        source_player_id_to_base_id[source_player["player_id"]] = base_player["player_id"]
        name_matches += 1

    merged_players = merge_player_rows(base_players, source_players, source_player_id_to_base_id)
    matched_base_ids = set(source_player_id_to_base_id.values())
    remapped_source_stat_lines = remap_source_stat_lines(source_stat_lines, source_player_id_to_base_id)
    if replace_timing:
        kept_base_stat_lines = [
            line
            for line in base_stat_lines
            if not (
                line.get("player_id") in matched_base_ids
                and line.get("timing", "").strip() == replace_timing
            )
        ]
    else:
        kept_base_stat_lines = base_stat_lines

    output_stat_lines = [
        *sorted(remapped_source_stat_lines, key=stat_line_sort_key),
        *kept_base_stat_lines,
    ]
    remapped_advanced_lines = remap_source_stat_lines(
        source_advanced_lines,
        source_player_id_to_base_id,
    )
    if replace_timing:
        kept_advanced_lines = [
            line
            for line in base_advanced_lines
            if not (
                line.get("player_id") in matched_base_ids
                and line.get("timing", "").strip() == replace_timing
            )
        ]
    else:
        kept_advanced_lines = base_advanced_lines

    write_table(output_root / "players.csv", PLAYER_COLUMNS, merged_players)
    write_table(output_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(
        output_root / "advanced_stat_lines.csv",
        ADVANCED_STAT_LINE_COLUMNS,
        [*remapped_advanced_lines, *kept_advanced_lines],
    )
    write_table(
        output_root / "unmatched_source_players.csv",
        PLAYER_COLUMNS,
        sort_rows(unmatched_source_players, "name"),
    )
    copy_passthrough_tables(base_root, output_root)

    return NormalizedMergeSummary(
        base_players=len(base_players),
        source_players=len(source_players),
        matched_players=len(source_player_id_to_base_id),
        manual_matches=manual_matches,
        name_matches=name_matches,
        unmatched_source_players=len(unmatched_source_players),
        source_stat_lines=len(source_stat_lines),
        output_stat_lines=len(output_stat_lines),
    )


def generate_match_map_template(
    base_dir: str | Path,
    unmatched_source_players_path: str | Path,
    output_path: str | Path,
    *,
    candidate_count: int = 3,
) -> list[dict[str, str]]:
    if candidate_count < 1:
        raise ValueError("candidate_count must be at least 1")

    base_players = read_table(Path(base_dir) / "players.csv")
    unmatched_players = read_table(Path(unmatched_source_players_path))
    rows: list[dict[str, str]] = []
    for source_player in unmatched_players:
        candidates = closest_base_players(source_player.get("name", ""), base_players, candidate_count)
        rows.append(build_match_template_row(source_player, candidates))

    write_table(Path(output_path), MATCH_MAP_TEMPLATE_COLUMNS, rows)
    return rows


def closest_base_players(
    source_name: str,
    base_players: list[dict[str, str]],
    candidate_count: int,
) -> list[tuple[dict[str, str], float]]:
    source_key = name_key(source_name)
    scored = [
        (base_player, SequenceMatcher(None, source_key, name_key(base_player["name"])).ratio())
        for base_player in base_players
    ]
    return sorted(scored, key=lambda item: (-item[1], item[0]["name"]))[:candidate_count]


def build_match_template_row(
    source_player: dict[str, str],
    candidates: list[tuple[dict[str, str], float]],
) -> dict[str, str]:
    row = {
        "source_player_id": source_player.get("player_id", ""),
        "source_name": source_player.get("name", ""),
        "base_player_id": "",
        "suggested_base_player_id": "",
        "suggested_base_name": "",
        "suggested_score": "",
        "candidate_2_base_player_id": "",
        "candidate_2_name": "",
        "candidate_2_score": "",
        "candidate_3_base_player_id": "",
        "candidate_3_name": "",
        "candidate_3_score": "",
        "note": "",
    }
    for index, (candidate, score) in enumerate(candidates[:3], start=1):
        if index == 1:
            row["suggested_base_player_id"] = candidate["player_id"]
            row["suggested_base_name"] = candidate["name"]
            row["suggested_score"] = f"{score:.3f}"
        else:
            row[f"candidate_{index}_base_player_id"] = candidate["player_id"]
            row[f"candidate_{index}_name"] = candidate["name"]
            row[f"candidate_{index}_score"] = f"{score:.3f}"
    return row


def merge_player_rows(
    base_players: list[dict[str, str]],
    source_players: list[dict[str, str]],
    source_player_id_to_base_id: dict[str, str],
) -> list[dict[str, str]]:
    source_by_base_id = {
        base_id: source_player
        for source_player in source_players
        if (base_id := source_player_id_to_base_id.get(source_player["player_id"]))
    }
    merged: list[dict[str, str]] = []
    for base_player in base_players:
        source_player = source_by_base_id.get(base_player["player_id"])
        if source_player is None:
            merged.append(base_player)
            continue
        row = dict(base_player)
        for column in ("birth_date", "nationality", "position", "handedness", "height_cm", "weight_kg", "age_at_draft"):
            if source_player.get(column):
                row[column] = source_player[column]
        row["source"] = source_player.get("source", row.get("source", ""))
        row["source_id"] = source_player.get("source_id", row.get("source_id", ""))
        row["source_url"] = source_player.get("source_url", row.get("source_url", ""))
        merged.append(row)
    return merged


def remap_source_stat_lines(
    source_stat_lines: list[dict[str, str]],
    source_player_id_to_base_id: dict[str, str],
) -> list[dict[str, str]]:
    remapped: list[dict[str, str]] = []
    for line in source_stat_lines:
        base_id = source_player_id_to_base_id.get(line["player_id"])
        if not base_id:
            continue
        row = dict(line)
        row["player_id"] = base_id
        remapped.append(row)
    return remapped


def copy_passthrough_tables(base_root: Path, output_root: Path) -> None:
    for filename in PASSTHROUGH_TABLES:
        source = base_root / filename
        if source.exists():
            shutil.copyfile(source, output_root / filename)


def read_match_map(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    rows = read_table(Path(path))
    mapped: dict[str, str] = {}
    for row in rows:
        source_player_id = row.get("source_player_id", "").strip()
        base_player_id = row.get("base_player_id", "").strip()
        if not source_player_id or not base_player_id:
            raise ValueError("match map rows require source_player_id and base_player_id")
        if source_player_id in mapped:
            raise ValueError(f"duplicate match map source_player_id={source_player_id}")
        mapped[source_player_id] = base_player_id
    return mapped


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"missing required table: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def read_optional_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_table(path)


def write_table(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sort_rows(rows: list[dict[str, str]], column: str) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: row.get(column, ""))


def stat_line_sort_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("player_id", ""),
        row.get("timing", ""),
        row.get("season", ""),
        row.get("league", ""),
    )


def name_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
