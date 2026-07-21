"""Normalize official Swedish, Finnish, and cached Russian league statistics."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from draft_room_intelligence.data.chl_stats import (
    count_normalized_names,
    normalize_person_key,
    read_drafted_league_hints,
    read_table,
)
from draft_room_intelligence.data.eliteprospects_csv import (
    ADVANCED_STAT_LINE_COLUMNS,
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name

EUROPE_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "provider",
    "league",
    "source_name",
    "source_id",
    "source_url",
    "team",
    "games",
    "points",
    "save_percentage",
]

LEAGUE_FAMILIES = {
    "sweden": {"SHL", "HockeyAllsvenskan", "Sweden Jrs."},
    "finland": {"Liiga", "Mestis", "Finland Jrs."},
    "russia": {"KHL", "VHL", "MHL"},
}


@dataclass(frozen=True)
class EuropeStatSource:
    season: str
    provider: str
    league: str
    source_url: str
    regular_season: bool = True
    kind: str = "combined"
    source_path: Path | None = None


@dataclass(frozen=True)
class EuropeStatLine:
    name: str
    source_id: str
    source_url: str
    provider: str
    league: str
    season: str
    regular_season: bool
    team: str
    games: str
    goals: str = ""
    assists: str = ""
    points: str = ""
    goalie_minutes: str = ""
    saves: str = ""
    goals_against: str = ""
    save_percentage: str = ""
    goals_against_average: str = ""
    wins: str = ""
    losses: str = ""
    ties: str = ""
    shutouts: str = ""
    plus_minus: str = ""
    shots: str = ""
    blocks: str = ""
    faceoff_wins: str = ""
    faceoff_losses: str = ""
    faceoff_percentage: str = ""


@dataclass(frozen=True)
class EuropeStatsEnrichmentSummary:
    players_scanned: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    output_advanced_lines: int
    match_report_path: Path


def enrich_europe_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    sources: list[EuropeStatSource],
) -> EuropeStatsEnrichmentSummary:
    source_root = Path(base_dir)
    target_root = Path(output_dir)
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    players = read_table(source_root / "players.csv")
    base_stats = read_table(source_root / "season_stat_lines.csv")
    advanced_path = source_root / "advanced_stat_lines.csv"
    base_advanced = read_table(advanced_path) if advanced_path.is_file() else []
    drafted_leagues = read_drafted_league_hints(source_root)
    source_lines = load_europe_source_lines(sources)
    by_name: dict[str, list[EuropeStatLine]] = {}
    for line in source_lines:
        by_name.setdefault(normalize_person_key(line.name), []).append(line)

    name_counts = count_normalized_names(players)
    matched: dict[str, list[EuropeStatLine]] = {}
    report: list[dict[str, str]] = []
    for player in players:
        player_id = player["player_id"]
        leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stats
            if row.get("player_id") == player_id
        }
        leagues.update(drafted_leagues.get(player_id, set()))
        key = normalize_person_key(player["name"])
        candidates = [line for line in by_name.get(key, []) if same_league_family(leagues, line)]
        if name_counts.get(key) == 1 and candidates:
            matched[player_id] = candidates
            report.extend(build_match_row(player, line, True) for line in candidates)
        else:
            report.append(build_match_row(player, None, False))

    candidate_keys = {
        (player_id, line.season, line.league, line.regular_season)
        for player_id, lines in matched.items()
        for line in lines
    }
    existing_games: dict[tuple[str, str, str, bool], int] = {}
    for row in base_stats:
        key = stat_key(row)
        if key in candidate_keys:
            existing_games[key] = max(existing_games.get(key, 0), integer(row.get("games", "")))
    replacement_keys = {
        key
        for key in candidate_keys
        if max(
            integer(line.games)
            for player_id, lines in matched.items()
            for line in lines
            if (player_id, line.season, line.league, line.regular_season) == key
        )
        >= existing_games.get(key, 0)
    }
    output_stats = [row for row in base_stats if stat_key(row) not in replacement_keys]
    output_advanced = [row for row in base_advanced if stat_key(row) not in replacement_keys]
    for player_id, lines in sorted(matched.items()):
        output_stats.extend(
            build_stat_line(player_id, line)
            for line in lines
            if (player_id, line.season, line.league, line.regular_season) in replacement_keys
        )
        output_advanced.extend(
            build_advanced_line(player_id, line) for line in lines if has_advanced_stats(line)
        )

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stats)
    write_table(
        target_root / "advanced_stat_lines.csv", ADVANCED_STAT_LINE_COLUMNS, output_advanced
    )
    write_table(target_root / "europe_stat_matches.csv", EUROPE_MATCH_COLUMNS, report)
    return EuropeStatsEnrichmentSummary(
        len(players),
        len(source_lines),
        len(matched),
        len(output_stats),
        len(output_advanced),
        target_root / "europe_stat_matches.csv",
    )


def load_europe_source_lines(sources: list[EuropeStatSource]) -> list[EuropeStatLine]:
    lines: list[EuropeStatLine] = []
    for source in sources:
        if source.source_path is None:
            raise ValueError("European source requires a collected cache")
        raw = source.source_path.read_text(encoding="utf-8")
        if source.provider == "swehockey":
            lines.extend(parse_swehockey(raw, source))
        elif source.provider == "liiga":
            lines.extend(parse_liiga(raw, source))
        elif source.provider == "khl":
            lines.extend(parse_khl_html(raw, source))
        else:
            raise ValueError(f"unsupported European provider: {source.provider}")
    return lines


class HtmlTableParser(HTMLParser):
    def __init__(self, table_class: str | None = None) -> None:
        super().__init__()
        self.table_class = table_class
        self.table_depth = 0
        self.target_depth = 0
        self.in_cell = False
        self.cell: list[str] = []
        self.href = ""
        self.row: list[tuple[str, str]] = []
        self.table: list[list[tuple[str, str]]] = []
        self.tables: list[list[list[tuple[str, str]]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self.table_depth += 1
            classes = (attributes.get("class") or "").split()
            if not self.target_depth and (self.table_class is None or self.table_class in classes):
                self.target_depth = self.table_depth
                self.table = []
        elif self.target_depth and tag in {"th", "td"}:
            self.in_cell = True
            self.cell = []
            self.href = ""
        elif self.in_cell and tag == "a":
            self.href = attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.target_depth and tag in {"th", "td"} and self.in_cell:
            value = re.sub(r"\s+", " ", "".join(self.cell)).strip()
            self.row.append((value, self.href))
            self.in_cell = False
        elif self.target_depth and tag == "tr" and self.table_depth == self.target_depth:
            if self.row:
                self.table.append(self.row)
            self.row = []
        elif tag == "table":
            if self.target_depth == self.table_depth:
                if self.table:
                    self.tables.append(self.table)
                self.target_depth = 0
                self.table = []
                self.row = []
            self.table_depth -= 1


def parse_swehockey(raw: str, source: EuropeStatSource) -> list[EuropeStatLine]:
    parser = HtmlTableParser("tblContent")
    parser.feed(raw)
    lines: list[EuropeStatLine] = []
    current_team = ""
    for table in parser.tables:
        section = ""
        headers: list[str] = []
        for row in table:
            values = [cell[0] for cell in row]
            if values and values[0] in {"Playing Statistics", "Goalkeeping Statistics"}:
                section = values[0]
                headers = []
            elif "Name" in values and ({"GP", "TP"} & set(values) or "GPI" in values):
                headers = values
            elif not section and not headers and values and values[0]:
                current_team = values[0].removesuffix("[Top]").strip()
            elif headers and (line := swehockey_row(headers, row, current_team, section, source)):
                lines.append(line)
    if not lines:
        raise ValueError("Swehockey payload has no player statistics")
    return lines


def swehockey_row(
    headers: list[str],
    row: list[tuple[str, str]],
    team: str,
    section: str,
    source: EuropeStatSource,
) -> EuropeStatLine | None:
    values = {
        header: row[index][0] if index < len(row) else "" for index, header in enumerate(headers)
    }
    name = display_swedish_name(values.get("Name", ""))
    if not name:
        return None
    common = (
        name,
        normalize_person_key(name),
        source.source_url,
        source.provider,
        source.league,
        source.season,
        source.regular_season,
        team,
    )
    if section == "Goalkeeping Statistics":
        return EuropeStatLine(
            *common,
            values.get("GPI", ""),
            goalie_minutes=values.get("MIP", ""),
            saves=values.get("SVS", ""),
            goals_against=values.get("GA", ""),
            save_percentage=percent_to_decimal(values.get("SVS%", "")),
            goals_against_average=values.get("GAA", ""),
            wins=values.get("W", ""),
            losses=values.get("L", ""),
            shutouts=values.get("SO", ""),
        )
    return EuropeStatLine(
        *common,
        values.get("GP", ""),
        values.get("G", ""),
        values.get("A", ""),
        values.get("TP", ""),
        plus_minus=values.get("+/-", ""),
        shots=values.get("SOG", ""),
        faceoff_wins=values.get("FO+", ""),
        faceoff_losses=values.get("FO-", ""),
        faceoff_percentage=values.get("FO%", ""),
    )


def parse_liiga(raw: str, source: EuropeStatSource) -> list[EuropeStatLine]:
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Liiga payload must be a player list")
    lines = [line for row in payload if isinstance(row, dict) if (line := liiga_row(row, source))]
    if not lines:
        raise ValueError("Liiga payload has no player statistics")
    return lines


def liiga_row(row: dict[str, object], source: EuropeStatSource) -> EuropeStatLine | None:
    name = " ".join(str(row.get(field, "")).strip() for field in ("firstName", "lastName")).strip()
    if not name or not row.get("games"):
        return None
    common = (
        name,
        str(row.get("playerId", normalize_person_key(name))),
        source.source_url,
        source.provider,
        source.league,
        source.season,
        source.regular_season,
        str(row.get("teamName", "")),
        value(row, "games"),
    )
    if source.kind == "goalies" or row.get("goalkeeper") is True:
        return EuropeStatLine(
            *common,
            goalie_minutes=value(row, "timeOnIce"),
            saves=value(row, "saves"),
            goals_against=value(row, "goalsAgainst"),
            save_percentage=normalize_save_percentage(row.get("savePercentage")),
            goals_against_average=value(row, "goalsAgainstAverage"),
            wins=value(row, "wins"),
            losses=value(row, "losses"),
            shutouts=value(row, "shutouts"),
        )
    return EuropeStatLine(
        *common,
        goals=value(row, "goals"),
        assists=value(row, "assists"),
        points=value(row, "points"),
        plus_minus=value(row, "plusMinus"),
        shots=value(row, "shots"),
        faceoff_wins=value(row, "contestWon"),
        faceoff_losses=value(row, "contestLost"),
        faceoff_percentage=value(row, "contestWonPercentage"),
    )


def parse_khl_html(raw: str, source: EuropeStatSource) -> list[EuropeStatLine]:
    parser = HtmlTableParser()
    parser.feed(raw)
    lines: list[EuropeStatLine] = []
    for table in parser.tables:
        header_index = next(
            (index for index, row in enumerate(table) if "Player" in [cell[0] for cell in row]),
            -1,
        )
        if header_index < 0:
            continue
        headers = [cell[0] for cell in table[header_index]]
        for row in table[header_index + 1 :]:
            values = {
                header: row[index][0] if index < len(row) else ""
                for index, header in enumerate(headers)
            }
            name = values.get("Player", "")
            if not name or not values.get("GP"):
                continue
            lines.append(
                EuropeStatLine(
                    name,
                    normalize_person_key(name),
                    source.source_url,
                    source.provider,
                    source.league,
                    source.season,
                    source.regular_season,
                    values.get("Team", ""),
                    values.get("GP", ""),
                    values.get("G", ""),
                    values.get("A", values.get("Assists", "")),
                    values.get("PTS", ""),
                    plus_minus=values.get("+/-", ""),
                )
            )
    if not lines:
        raise ValueError("KHL-family payload has no complete player statistics table")
    return lines


def same_league_family(leagues: set[str], line: EuropeStatLine) -> bool:
    provider_family = {"swehockey": "sweden", "liiga": "finland", "khl": "russia"}[line.provider]
    return bool(leagues & LEAGUE_FAMILIES[provider_family])


def stat_key(row: dict[str, str]) -> tuple[str, str, str, bool] | None:
    if row.get("timing") != "pre_draft":
        return None
    return (
        row.get("player_id", ""),
        row.get("season", ""),
        normalize_league_name(row.get("league", "")),
        row.get("regular_season", "true").casefold() == "true",
    )


def build_stat_line(player_id: str, line: EuropeStatLine) -> dict[str, str]:
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
        "regular_season": str(line.regular_season).lower(),
        "goalie_minutes": line.goalie_minutes,
        "saves": line.saves,
        "goals_against": line.goals_against,
        "save_percentage": line.save_percentage,
        "goals_against_average": line.goals_against_average,
        "wins": line.wins,
        "losses": line.losses,
        "ties": line.ties,
        "shutouts": line.shutouts,
        "source": line.provider,
        "source_id": line.source_id,
        "source_url": line.source_url,
    }


def build_advanced_line(player_id: str, line: EuropeStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": line.league,
        "team": line.team,
        "timing": "pre_draft",
        "regular_season": str(line.regular_season).lower(),
        "games": line.games,
        "plus_minus": line.plus_minus,
        "shots": line.shots,
        "blocks": line.blocks,
        "faceoff_wins": line.faceoff_wins,
        "faceoff_losses": line.faceoff_losses,
        "faceoff_percentage": line.faceoff_percentage,
        "source": line.provider,
        "source_id": line.source_id,
        "source_url": line.source_url,
    }


def has_advanced_stats(line: EuropeStatLine) -> bool:
    return any(
        (
            line.plus_minus,
            line.shots,
            line.blocks,
            line.faceoff_wins,
            line.faceoff_losses,
            line.faceoff_percentage,
        )
    )


def build_match_row(
    player: dict[str, str], line: EuropeStatLine | None, matched: bool
) -> dict[str, str]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": str(matched).lower(),
        "provider": line.provider if line else "",
        "league": line.league if line else "",
        "source_name": line.name if line else "",
        "source_id": line.source_id if line else "",
        "source_url": line.source_url if line else "",
        "team": line.team if line else "",
        "games": line.games if line else "",
        "points": line.points if line else "",
        "save_percentage": line.save_percentage if line else "",
    }


def display_swedish_name(name: str) -> str:
    last, separator, first = name.partition(",")
    return f"{first.strip()} {last.strip()}" if separator else name.strip()


def percent_to_decimal(value_text: str) -> str:
    try:
        return f"{float(value_text) / 100:.3f}"
    except (TypeError, ValueError):
        return ""


def normalize_save_percentage(raw: object) -> str:
    try:
        value_number = float(raw)
    except (TypeError, ValueError):
        return ""
    if value_number > 1:
        value_number /= 100
    return f"{value_number:.3f}"


def value(row: dict[str, object], key: str) -> str:
    raw = row.get(key, "")
    return "" if raw is None else str(raw)


def integer(raw: object) -> int:
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return 0
