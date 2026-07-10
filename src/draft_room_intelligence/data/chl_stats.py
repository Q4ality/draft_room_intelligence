"""Import public CHL stat-table pages into normalized season stat lines."""

from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name


CHL_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "league",
    "source_name",
    "source_id",
    "source_url",
    "team",
    "games",
    "goals",
    "assists",
    "points",
]


@dataclass(frozen=True)
class ChlStatSource:
    league: str
    season: str
    source_url: str
    source_path: Path | None = None


@dataclass(frozen=True)
class ChlSkaterStatLine:
    name: str
    source_id: str
    source_url: str
    league: str
    season: str
    team: str
    games: str
    goals: str
    assists: str
    points: str


@dataclass(frozen=True)
class ChlStatsEnrichmentSummary:
    players_scanned: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    match_report_path: Path


def enrich_chl_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    sources: list[ChlStatSource],
) -> ChlStatsEnrichmentSummary:
    source_root = Path(base_dir)
    target_root = Path(output_dir)
    if not source_root.exists():
        raise ValueError(f"missing base dataset directory: {source_root}")

    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    players = read_table(source_root / "players.csv")
    base_stat_lines = read_table(source_root / "season_stat_lines.csv")
    source_lines = load_chl_source_lines(sources)
    source_by_name_league = {
        (normalize_person_key(line.name), normalize_league_name(line.league)): line
        for line in source_lines
    }

    matched_by_player_id: dict[str, ChlSkaterStatLine] = {}
    report_rows: list[dict[str, str]] = []
    for player in players:
        player_leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stat_lines
            if row.get("player_id") == player["player_id"]
        }
        candidates = [
            source_by_name_league[(normalize_person_key(player["name"]), league)]
            for league in player_leagues
            if (normalize_person_key(player["name"]), league) in source_by_name_league
        ]
        if len(candidates) == 1:
            matched_by_player_id[player["player_id"]] = candidates[0]
            report_rows.append(build_match_row(player, candidates[0], matched=True))
        else:
            report_rows.append(build_match_row(player, None, matched=False))

    output_stat_lines = [
        row
        for row in base_stat_lines
        if not (
            row.get("timing") == "pre_draft"
            and row.get("player_id") in matched_by_player_id
            and normalize_league_name(row.get("league", ""))
            == normalize_league_name(matched_by_player_id[row["player_id"]].league)
        )
    ]
    output_stat_lines.extend(
        build_normalized_stat_line(player_id, line)
        for player_id, line in sorted(matched_by_player_id.items())
    )

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(target_root / "chl_stat_matches.csv", CHL_MATCH_COLUMNS, report_rows)

    return ChlStatsEnrichmentSummary(
        players_scanned=len(players),
        source_rows=len(source_lines),
        matched_players=len(matched_by_player_id),
        output_stat_lines=len(output_stat_lines),
        match_report_path=target_root / "chl_stat_matches.csv",
    )


def load_chl_source_lines(sources: list[ChlStatSource]) -> list[ChlSkaterStatLine]:
    lines: list[ChlSkaterStatLine] = []
    for source in sources:
        html = source.source_path.read_text(encoding="utf-8") if source.source_path else fetch_text(source.source_url)
        lines.extend(parse_chl_skaters_html(html, source))
    return lines


def parse_chl_skaters_html(html: str, source: ChlStatSource) -> list[ChlSkaterStatLine]:
    data = extract_datatable_data(html, "topskaters")
    lines: list[ChlSkaterStatLine] = []
    for row in data:
        if len(row) < 11 or not isinstance(row[5], list):
            continue
        player_url, raw_name = row[5]
        teams = row[6] if isinstance(row[6], list) else []
        lines.append(
            ChlSkaterStatLine(
                name=normalize_chl_player_name(str(raw_name)),
                source_id=source_id_from_url(str(player_url)),
                source_url=str(player_url),
                league=normalize_league_name(source.league),
                season=source.season,
                team="/".join(str(team[-1]) for team in teams if isinstance(team, list) and team),
                games=str(row[7]),
                goals=str(row[8]),
                assists=str(row[9]),
                points=str(row[10]),
            )
        )
    return lines


def extract_datatable_data(html: str, table_id: str) -> list[list[object]]:
    table_marker = f'id="{table_id}"'
    table_index = html.find(table_marker)
    if table_index == -1:
        return []
    data_index = html.find("data:", table_index)
    if data_index == -1:
        return []
    bracket_index = html.find("[", data_index)
    if bracket_index == -1:
        return []
    data_text = extract_balanced_brackets(html, bracket_index)
    return json.loads(data_text)


def extract_balanced_brackets(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("could not find balanced CHL data array")


def build_normalized_stat_line(player_id: str, line: ChlSkaterStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": line.league,
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true",
        "source": "chl",
        "source_id": line.source_id,
        "source_url": line.source_url,
    }


def build_match_row(
    player: dict[str, str],
    line: ChlSkaterStatLine | None,
    *,
    matched: bool,
) -> dict[str, str]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": "true" if matched else "false",
        "league": line.league if line else "",
        "source_name": line.name if line else "",
        "source_id": line.source_id if line else "",
        "source_url": line.source_url if line else "",
        "team": line.team if line else "",
        "games": line.games if line else "",
        "goals": line.goals if line else "",
        "assists": line.assists if line else "",
        "points": line.points if line else "",
    }


def normalize_chl_player_name(value: str) -> str:
    if "," not in value:
        return value.strip()
    last, first = [part.strip() for part in value.split(",", 1)]
    return f"{first} {last}".strip()


def normalize_person_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def source_id_from_url(value: str) -> str:
    parsed = urlparse(value)
    return parsed.path.rstrip("/").split("/")[-1]


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "draft-room-intelligence/0.1"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))
