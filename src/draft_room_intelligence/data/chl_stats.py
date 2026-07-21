"""Import public CHL stat-table pages into normalized season stat lines."""

from __future__ import annotations

import csv
import json
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
    "regular_season",
]


@dataclass(frozen=True)
class ChlStatSource:
    league: str
    season: str
    source_url: str
    regular_season: bool = True
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
    regular_season: bool
    goalie_minutes: str = ""
    shots_against: str = ""
    saves: str = ""
    goals_against: str = ""
    save_percentage: str = ""
    goals_against_average: str = ""
    wins: str = ""
    losses: str = ""
    ties: str = ""
    shutouts: str = ""


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
    drafted_leagues = read_drafted_league_hints(source_root)
    source_lines = load_chl_source_lines(sources)
    source_by_name_league: dict[tuple[str, str], list[ChlSkaterStatLine]] = {}
    for line in source_lines:
        key = (normalize_person_key(line.name), normalize_league_name(line.league))
        source_by_name_league.setdefault(key, []).append(line)

    matched_by_player_id: dict[str, list[ChlSkaterStatLine]] = {}
    report_rows: list[dict[str, str]] = []
    player_name_counts = count_normalized_names(players)
    for player in players:
        player_leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stat_lines
            if row.get("player_id") == player["player_id"]
        }
        player_leagues.update(drafted_leagues.get(player["player_id"], set()))
        candidates: list[ChlSkaterStatLine] = []
        player_key = normalize_person_key(player["name"])
        if player_name_counts.get(player_key) == 1:
            for league in player_leagues:
                candidates.extend(source_by_name_league.get((player_key, league), []))
        candidates = deduplicate_chl_lines(candidates)
        if candidates:
            matched_by_player_id[player["player_id"]] = candidates
            for candidate in candidates:
                report_rows.append(build_match_row(player, candidate, matched=True))
        else:
            report_rows.append(build_match_row(player, None, matched=False))

    matched_leagues_by_player = {
        player_id: {normalize_league_name(line.league) for line in lines}
        for player_id, lines in matched_by_player_id.items()
    }
    output_stat_lines = [
        row
        for row in base_stat_lines
        if not (
            row.get("timing") == "pre_draft"
            and row.get("player_id") in matched_by_player_id
            and row.get("source") in {"wikipedia", "chl"}
            and normalize_league_name(row.get("league", ""))
            in matched_leagues_by_player[row["player_id"]]
        )
    ]
    for player_id, lines in sorted(matched_by_player_id.items()):
        output_stat_lines.extend(build_normalized_stat_line(player_id, line) for line in lines)

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
        lines.extend(parse_chl_goalies_html(html, source))
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
                regular_season=source.regular_season,
            )
        )
    return lines


def parse_chl_goalies_html(html: str, source: ChlStatSource) -> list[ChlSkaterStatLine]:
    data = extract_datatable_data(html, "topgoalies")
    lines: list[ChlSkaterStatLine] = []
    for row in data:
        if len(row) < 8 or not isinstance(row[5], list):
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
                goals="",
                assists="",
                points="",
                regular_season=source.regular_season,
                goalie_minutes=str(row[8]),
                shots_against=str(row[9]),
                saves=str(row[10]),
                goals_against=str(row[11]),
                shutouts=str(row[12]),
                goals_against_average=str(row[13]),
                save_percentage=str(row[14]),
                wins=str(row[15]),
                losses=str(row[16]),
                ties=str(row[17]) if len(row) > 17 else "",
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
        "regular_season": "true" if line.regular_season else "false",
        "source": "chl",
        "source_id": line.source_id,
        "source_url": line.source_url,
        "goalie_minutes": line.goalie_minutes,
        "shots_against": line.shots_against,
        "saves": line.saves,
        "goals_against": line.goals_against,
        "save_percentage": line.save_percentage,
        "goals_against_average": line.goals_against_average,
        "wins": line.wins,
        "losses": line.losses,
        "ties": line.ties,
        "shutouts": line.shutouts,
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
        "regular_season": "true" if line and line.regular_season else "false",
    }


def deduplicate_chl_lines(lines: list[ChlSkaterStatLine]) -> list[ChlSkaterStatLine]:
    by_key: dict[tuple[str, str, bool], ChlSkaterStatLine] = {}
    for line in lines:
        key = (normalize_league_name(line.league), normalize_person_key(line.team), line.regular_season)
        existing = by_key.get(key)
        if existing is not None and (has_goalie_metrics(existing) or not has_goalie_metrics(line)):
            continue
        by_key[key] = line
    return list(by_key.values())


def has_goalie_metrics(line: ChlSkaterStatLine) -> bool:
    return any(
        (
            line.goalie_minutes,
            line.shots_against,
            line.saves,
            line.goals_against,
            line.save_percentage,
            line.goals_against_average,
        )
    )


def normalize_chl_player_name(value: str) -> str:
    if "," not in value:
        return value.strip()
    last, first = [part.strip() for part in value.split(",", 1)]
    return f"{first} {last}".strip()


def normalize_person_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def count_normalized_names(players: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for player in players:
        key = normalize_person_key(player.get("name", ""))
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def read_drafted_league_hints(dataset_root: Path) -> dict[str, set[str]]:
    path = dataset_root / "draft_selections.csv"
    if not path.is_file():
        return {}
    hints: dict[str, set[str]] = {}
    for row in read_table(path):
        league = normalize_league_name(row.get("drafted_from_league", ""))
        if league:
            hints.setdefault(row.get("player_id", ""), set()).add(league)
    return hints


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
