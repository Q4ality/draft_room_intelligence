"""Import official USHL HockeyTech feeds into normalized season stat lines."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from draft_room_intelligence.data.chl_stats import (
    count_normalized_names,
    fetch_text,
    normalize_person_key,
    read_drafted_league_hints,
    read_table,
)
from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name

USHL_APP_KEY = "e828f89b243dc43f"
USHL_CLIENT_CODE = "ushl"
USHL_LEAGUE_ID = "1"
USHL_SEASON_CATALOG_URL = (
    "https://lscluster.hockeytech.com/feed/"
    "?feed=modulekit&view=seasons&lang=en"
    f"&key={USHL_APP_KEY}&fmt=json&client_code={USHL_CLIENT_CODE}"
)
USHL_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
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
class UShlStatSource:
    season: str
    season_id: str
    regular_season: bool
    source_url: str | None = None
    source_path: Path | None = None
    position: str = "skaters"


@dataclass(frozen=True)
class UShlSkaterStatLine:
    name: str
    source_id: str
    source_url: str
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
class UShlStatsEnrichmentSummary:
    players_scanned: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    match_report_path: Path


def enrich_ushl_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    sources: list[UShlStatSource],
) -> UShlStatsEnrichmentSummary:
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
    source_lines = load_ushl_source_lines(sources)
    source_by_name: dict[str, list[UShlSkaterStatLine]] = {}
    for line in source_lines:
        source_by_name.setdefault(normalize_person_key(line.name), []).append(line)

    matched_by_player_id: dict[str, list[UShlSkaterStatLine]] = {}
    report_rows: list[dict[str, str]] = []
    player_name_counts = count_normalized_names(players)
    for player in players:
        player_leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stat_lines
            if row.get("player_id") == player["player_id"]
        }
        player_leagues.update(drafted_leagues.get(player["player_id"], set()))
        candidates = source_by_name.get(normalize_person_key(player["name"]), [])
        if (
            player_name_counts.get(normalize_person_key(player["name"])) == 1
            and normalize_league_name("USHL") in player_leagues
            and candidates
        ):
            matched_by_player_id[player["player_id"]] = candidates
            for candidate in candidates:
                report_rows.append(build_match_row(player, candidate, matched=True))
        else:
            report_rows.append(build_match_row(player, None, matched=False))

    output_stat_lines = [
        row
        for row in base_stat_lines
        if not (
            row.get("timing") == "pre_draft"
            and row.get("player_id") in matched_by_player_id
            and normalize_league_name(row.get("league", "")) == normalize_league_name("USHL")
        )
    ]
    for player_id, lines in sorted(matched_by_player_id.items()):
        output_stat_lines.extend(build_normalized_stat_line(player_id, line) for line in lines)

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(target_root / "ushl_stat_matches.csv", USHL_MATCH_COLUMNS, report_rows)

    return UShlStatsEnrichmentSummary(
        players_scanned=len(players),
        source_rows=len(source_lines),
        matched_players=len(matched_by_player_id),
        output_stat_lines=len(output_stat_lines),
        match_report_path=target_root / "ushl_stat_matches.csv",
    )


def load_ushl_source_lines(sources: list[UShlStatSource]) -> list[UShlSkaterStatLine]:
    lines: list[UShlSkaterStatLine] = []
    for source in sources:
        raw = (
            source.source_path.read_text(encoding="utf-8")
            if source.source_path
            else fetch_text(source_url(source))
        )
        if source.position == "goalies":
            lines.extend(parse_ushl_goalies_json(raw, source))
        else:
            lines.extend(parse_ushl_skaters_json(raw, source))
    return lines


def parse_ushl_skaters_json(raw: str, source: UShlStatSource) -> list[UShlSkaterStatLine]:
    payload = parse_json_or_jsonp(raw)
    sections = payload[0].get("sections", []) if payload else []
    rows = sections[0].get("data", []) if sections else []
    lines: list[UShlSkaterStatLine] = []
    for entry in rows:
        row = entry.get("row", {})
        name = str(row.get("name", "")).strip()
        source_id = str(row.get("player_id", "")).strip()
        if not name or not source_id:
            continue
        lines.append(
            UShlSkaterStatLine(
                name=name,
                source_id=source_id,
                source_url=player_source_url(source_id, source.season_id, name),
                season=source.season,
                team=str(row.get("team_code", "")).strip(),
                games=str(row.get("games_played", "")).strip(),
                goals=str(row.get("goals", "")).strip(),
                assists=str(row.get("assists", "")).strip(),
                points=str(row.get("points", "")).strip(),
                regular_season=source.regular_season,
            )
        )
    return lines


def parse_ushl_goalies_json(raw: str, source: UShlStatSource) -> list[UShlSkaterStatLine]:
    payload = parse_json_or_jsonp(raw)
    sections = payload[0].get("sections", []) if payload else []
    rows = sections[0].get("data", []) if sections else []
    lines: list[UShlSkaterStatLine] = []
    for entry in rows:
        row = entry.get("row", {})
        name = str(row.get("name", "")).strip()
        source_id = str(row.get("player_id", "")).strip()
        if not name or not source_id:
            continue
        shots = stat_text(row.get("shots"))
        goals_against = stat_text(row.get("goals_against"))
        lines.append(
            UShlSkaterStatLine(
                name=name,
                source_id=source_id,
                source_url=player_source_url(source_id, source.season_id, name),
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
            )
        )
    return lines


def parse_json_or_jsonp(raw: str) -> list[dict[str, object]]:
    text = raw.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return json.loads(text)


def stat_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def calculate_saves(shots: str, goals_against: str) -> str:
    try:
        return str(int(shots) - int(goals_against))
    except ValueError:
        return ""


def source_url(source: UShlStatSource) -> str:
    if source.source_url:
        return source.source_url
    return (
        "https://lscluster.hockeytech.com/feed/index.php"
        "?feed=statviewfeed"
        "&view=players"
        f"&season={source.season_id}"
        "&team=all"
        f"&position={source.position}"
        "&rookies=0"
        "&statsType=standard"
        "&rosterstatus="
        "&site_id="
        "&first=0"
        "&limit=1000"
        f"&sort={'save_percentage' if source.position == 'goalies' else 'points'}"
        f"&league_id={USHL_LEAGUE_ID}"
        "&lang=en"
        "&division=-1"
        f"&key={USHL_APP_KEY}"
        f"&client_code={USHL_CLIENT_CODE}"
    )


def player_source_url(player_id: str, season_id: str, name: str) -> str:
    return f"https://ushl.com/ht/#/player/{player_id}/{season_id}/{quote(name)}"


def build_normalized_stat_line(player_id: str, line: UShlSkaterStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": "USHL",
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true" if line.regular_season else "false",
        "source": "ushl",
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
    line: UShlSkaterStatLine | None,
    *,
    matched: bool,
) -> dict[str, str]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": "true" if matched else "false",
        "source_name": line.name if line else "",
        "source_id": line.source_id if line else "",
        "source_url": line.source_url if line else "",
        "team": line.team if line else "",
        "games": line.games if line else "",
        "goals": line.goals if line else "",
        "assists": line.assists if line else "",
        "points": line.points if line else "",
        "regular_season": "true" if line and line.regular_season else "false" if line else "",
    }
