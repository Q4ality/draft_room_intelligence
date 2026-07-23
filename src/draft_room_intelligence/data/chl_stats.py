"""Import public CHL stat-table pages into normalized season stat lines."""

from __future__ import annotations

import csv
import json
import re
import shutil
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from draft_room_intelligence.data.eliteprospects_csv import (
    ADVANCED_STAT_LINE_COLUMNS,
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

CHL_HOCKEYTECH_CONFIG = {
    "OHL": {
        "base_url": "https://lscluster.hockeytech.com/feed/index.php",
        "client_code": "ohl",
        "key": "f1aa699db3d81487",
        "league_id": "1",
        "site_id": "1",
    },
    "WHL": {
        "base_url": "https://lscluster.hockeytech.com/feed/index.php",
        "client_code": "whl",
        "key": "f1aa699db3d81487",
        "league_id": "7",
        "site_id": "0",
    },
    "QMJHL": {
        "base_url": "https://cluster.leaguestat.com/feed/index.php",
        "client_code": "lhjmq",
        "key": "f322673b6bcae299",
        "league_id": "6",
        "site_id": "0",
    },
}

FIRST_NAME_ALIASES = {
    "egor": "yegor",
    "jack": "john",
    "jake": "jacob",
    "jc": "jeanchristophe",
    "mitch": "mitchell",
    "nick": "nicholas",
    "tony": "anthony",
    "will": "william",
}

CHL_CANCELED_STAGES = {("QMJHL", 2020, False)}


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
    plus_minus: str = ""


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
    advanced_path = source_root / "advanced_stat_lines.csv"
    base_advanced_lines = read_table(advanced_path) if advanced_path.is_file() else []
    drafted_leagues = read_drafted_league_hints(source_root)
    source_lines = load_chl_source_lines(sources)
    source_by_name_league: dict[tuple[str, str], list[ChlSkaterStatLine]] = {}
    source_by_alias_league: dict[tuple[str, str], list[ChlSkaterStatLine]] = {}
    source_by_redacted_league: dict[tuple[str, str], list[ChlSkaterStatLine]] = {}
    for line in source_lines:
        league = normalize_league_name(line.league)
        key = (normalize_person_key(line.name), league)
        source_by_name_league.setdefault(key, []).append(line)
        alias_key = person_alias_key(line.name)
        if alias_key:
            source_by_alias_league.setdefault((alias_key, league), []).append(line)
        redacted_key = redacted_source_name_key(line.name)
        if redacted_key:
            source_by_redacted_league.setdefault((redacted_key, league), []).append(line)

    matched_by_player_id: dict[str, list[ChlSkaterStatLine]] = {}
    report_rows: list[dict[str, str]] = []
    player_name_counts = count_normalized_names(players)
    player_alias_counts = count_player_keys(players, person_alias_key)
    player_redacted_counts = count_player_keys(players, player_redacted_name_key)
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
            if not candidates:
                alias_candidates: list[ChlSkaterStatLine] = []
                alias_key = person_alias_key(player["name"])
                for league in player_leagues:
                    alias_candidates.extend(source_by_alias_league.get((alias_key, league), []))
                if (
                    player_alias_counts.get(alias_key) == 1
                    and len({line.source_id for line in alias_candidates}) == 1
                ):
                    candidates.extend(alias_candidates)
            if not candidates:
                redacted_candidates: list[ChlSkaterStatLine] = []
                redacted_key = player_redacted_name_key(player["name"])
                for league in player_leagues:
                    redacted_candidates.extend(
                        source_by_redacted_league.get((redacted_key, league), [])
                    )
                if (
                    player_redacted_counts.get(redacted_key) == 1
                    and len({line.source_id for line in redacted_candidates}) == 1
                ):
                    candidates.extend(redacted_candidates)
        candidates = deduplicate_chl_lines(candidates)
        if candidates:
            matched_by_player_id[player["player_id"]] = candidates
            for candidate in candidates:
                report_rows.append(build_match_row(player, candidate, matched=True))
        else:
            report_rows.append(build_match_row(player, None, matched=False))

    matched_scopes = {
        (
            player_id,
            line.season,
            normalize_league_name(line.league),
            line.regular_season,
        )
        for player_id, lines in matched_by_player_id.items()
        for line in lines
    }
    output_stat_lines = [
        row
        for row in base_stat_lines
        if not (
            row.get("timing") == "pre_draft"
            and (
                row.get("player_id", ""),
                row.get("season", ""),
                normalize_league_name(row.get("league", "")),
                row.get("regular_season", "true").casefold() == "true",
            )
            in matched_scopes
        )
    ]
    for player_id, lines in sorted(matched_by_player_id.items()):
        output_stat_lines.extend(build_normalized_stat_line(player_id, line) for line in lines)
    matched_advanced_keys = {
        (
            player_id,
            line.season,
            normalize_league_name(line.league),
            "true" if line.regular_season else "false",
        )
        for player_id, lines in matched_by_player_id.items()
        for line in lines
        if line.plus_minus
    }
    output_advanced_lines = [
        row
        for row in base_advanced_lines
        if (
            row.get("player_id", ""),
            row.get("season", ""),
            normalize_league_name(row.get("league", "")),
            row.get("regular_season", ""),
        )
        not in matched_advanced_keys
    ]
    for player_id, lines in sorted(matched_by_player_id.items()):
        output_advanced_lines.extend(
            build_normalized_advanced_line(player_id, line)
            for line in lines
            if line.plus_minus
        )

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(
        target_root / "advanced_stat_lines.csv",
        ADVANCED_STAT_LINE_COLUMNS,
        output_advanced_lines,
    )
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
        html = (
            source.source_path.read_text(encoding="utf-8")
            if source.source_path
            else fetch_text(source.source_url)
        )
        if is_hockeytech_cache(html):
            lines.extend(parse_chl_hockeytech_json(html, source))
        else:
            lines.extend(parse_chl_skaters_html(html, source))
            lines.extend(parse_chl_goalies_html(html, source))
    return lines


def is_hockeytech_cache(raw: str) -> bool:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("provider") == "hockeytech"


def parse_chl_hockeytech_json(
    raw: str,
    source: ChlStatSource,
) -> list[ChlSkaterStatLine]:
    payload = json.loads(raw)
    lines: list[ChlSkaterStatLine] = []
    for position in ("skaters", "goalies"):
        sections = payload.get(position, [])
        section_rows = sections[0].get("sections", []) if sections else []
        rows = section_rows[0].get("data", []) if section_rows else []
        if not rows:
            raise ValueError(f"HockeyTech CHL cache has no {position} statistics")
        for entry in rows:
            row = entry.get("row", {})
            name = normalize_chl_player_name(str(row.get("name", "")))
            source_id = str(row.get("player_id", "")).strip()
            if not name or not source_id:
                continue
            if position == "goalies":
                shots = stat_text(row.get("shots"))
                goals_against = stat_text(row.get("goals_against"))
                lines.append(
                    ChlSkaterStatLine(
                        name=name,
                        source_id=source_id,
                        source_url=source.source_url,
                        league=normalize_league_name(source.league),
                        season=source.season,
                        team=stat_text(row.get("team_code")),
                        games=stat_text(row.get("games_played")),
                        goals="",
                        assists="",
                        points="",
                        regular_season=source.regular_season,
                        goalie_minutes=stat_text(row.get("minutes_played")),
                        shots_against=shots,
                        saves=calculate_saves(shots, goals_against),
                        goals_against=goals_against,
                        save_percentage=stat_text(row.get("save_percentage")),
                        goals_against_average=stat_text(row.get("goals_against_average")),
                        wins=stat_text(row.get("wins")),
                        losses=stat_text(row.get("losses")),
                        ties=stat_text(row.get("ot_losses")),
                        shutouts=stat_text(row.get("shutouts")),
                        plus_minus=stat_text(row.get("plus_minus")),
                    )
                )
            else:
                lines.append(
                    ChlSkaterStatLine(
                        name=name,
                        source_id=source_id,
                        source_url=source.source_url,
                        league=normalize_league_name(source.league),
                        season=source.season,
                        team=stat_text(row.get("team_code")),
                        games=stat_text(row.get("games_played")),
                        goals=stat_text(row.get("goals")),
                        assists=stat_text(row.get("assists")),
                        points=stat_text(row.get("points")),
                        regular_season=source.regular_season,
                        plus_minus=stat_text(row.get("plus_minus")),
                    )
                )
    return lines


def build_chl_hockeytech_urls(league: str, source_url: str) -> tuple[str, str]:
    league_name = normalize_league_name(league)
    config = CHL_HOCKEYTECH_CONFIG.get(league_name)
    if config is None:
        raise ValueError(f"unsupported CHL HockeyTech league: {league}")
    match = re.search(r"/stats/players/(\d+)", source_url)
    if not match:
        raise ValueError(f"CHL source URL has no season id: {source_url}")
    season_id = match.group(1)
    common = (
        f"{config['base_url']}?feed=statviewfeed&view=players"
        f"&season={season_id}&team=all&rookies=0&statsType=standard"
        f"&rosterstatus=&site_id={config['site_id']}&first=0&limit=2000"
        f"&league_id={config['league_id']}&lang=en&division=-1"
        f"&key={config['key']}&client_code={config['client_code']}"
    )
    return f"{common}&sort=points", f"{common}&position=goalies&sort=save_percentage"


def combine_chl_hockeytech_payloads(skaters_raw: str, goalies_raw: str) -> bytes:
    payload = {
        "provider": "hockeytech",
        "skaters": parse_json_or_jsonp(skaters_raw),
        "goalies": parse_json_or_jsonp(goalies_raw),
    }
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def parse_json_or_jsonp(raw: str) -> object:
    text = raw.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return json.loads(text)


def stat_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"n/a", "na", "-", "—"} else text


def calculate_saves(shots: str, goals_against: str) -> str:
    try:
        return str(int(shots) - int(goals_against))
    except ValueError:
        return ""


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
                games=stat_text(row[7]),
                goals=stat_text(row[8]),
                assists=stat_text(row[9]),
                points=stat_text(row[10]),
                regular_season=source.regular_season,
                plus_minus=stat_text(row[11]) if len(row) > 11 else "",
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
                games=stat_text(row[7]),
                goals="",
                assists="",
                points="",
                regular_season=source.regular_season,
                goalie_minutes=stat_text(row[8]),
                shots_against=stat_text(row[9]),
                saves=stat_text(row[10]),
                goals_against=stat_text(row[11]),
                shutouts=stat_text(row[12]),
                goals_against_average=stat_text(row[13]),
                save_percentage=stat_text(row[14]),
                wins=stat_text(row[15]),
                losses=stat_text(row[16]),
                ties=stat_text(row[17]) if len(row) > 17 else "",
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


def build_normalized_advanced_line(
    player_id: str,
    line: ChlSkaterStatLine,
) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": line.league,
        "team": line.team,
        "timing": "pre_draft",
        "regular_season": "true" if line.regular_season else "false",
        "games": line.games,
        "plus_minus": line.plus_minus,
        "shots": "",
        "blocks": "",
        "faceoff_wins": "",
        "faceoff_losses": "",
        "faceoff_percentage": "",
        "source": "chl",
        "source_id": line.source_id,
        "source_url": line.source_url,
    }


def deduplicate_chl_lines(lines: list[ChlSkaterStatLine]) -> list[ChlSkaterStatLine]:
    by_key: dict[tuple[str, str, str, bool], ChlSkaterStatLine] = {}
    for line in lines:
        key = (
            normalize_league_name(line.league),
            line.season,
            normalize_person_key(line.team),
            line.regular_season,
        )
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
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(character.lower() for character in ascii_value if character.isalnum())


def person_alias_key(value: str) -> str:
    parts = value.split()
    if len(parts) < 2:
        return ""
    first = normalize_person_key(parts[0])
    last = normalize_person_key(parts[-1])
    canonical_first = FIRST_NAME_ALIASES.get(first, first)
    return f"{canonical_first}{last}" if canonical_first and last else ""


def redacted_source_name_key(value: str) -> str:
    parts = value.split()
    if len(parts) != 2:
        return ""
    first = normalize_person_key(parts[0])
    last = normalize_person_key(parts[1])
    return f"{first}{last}" if first and len(last) == 1 else ""


def player_redacted_name_key(value: str) -> str:
    parts = value.split()
    if len(parts) < 2:
        return ""
    first = normalize_person_key(parts[0])
    last = normalize_person_key(parts[-1])
    return f"{first}{last[:1]}" if first and last else ""


def count_normalized_names(players: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for player in players:
        key = normalize_person_key(player.get("name", ""))
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def count_player_keys(
    players: list[dict[str, str]],
    key_builder: Callable[[str], str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for player in players:
        key = key_builder(player.get("name", ""))
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
