"""Normalize national NCAA Division I skater and goalie statistics."""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from draft_room_intelligence.data.chl_stats import (
    count_normalized_names,
    normalize_person_key,
    person_alias_key,
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

NCAA_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "disposition",
    "source_availability",
    "provider",
    "source_name",
    "source_id",
    "source_url",
    "team",
    "games",
    "points",
    "save_percentage",
]


@dataclass(frozen=True)
class NcaaStatSource:
    season: str
    provider: str
    source_url: str
    kind: str = "combined"
    source_path: Path | None = None


@dataclass(frozen=True)
class NcaaStatLine:
    name: str
    source_id: str
    source_url: str
    provider: str
    season: str
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
class NcaaStatsEnrichmentSummary:
    players_scanned: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    output_advanced_lines: int
    match_report_path: Path
    source_availability: str
    disposition_counts: dict[str, int]


def enrich_ncaa_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    sources: list[NcaaStatSource],
) -> NcaaStatsEnrichmentSummary:
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
    available_sources, source_availability = classify_available_sources(sources)
    source_lines = load_ncaa_source_lines(available_sources)
    by_name: dict[str, list[NcaaStatLine]] = {}
    by_alias: dict[str, list[NcaaStatLine]] = {}
    for line in source_lines:
        by_name.setdefault(normalize_person_key(line.name), []).append(line)
        by_alias.setdefault(person_alias_key(line.name), []).append(line)

    matched: dict[str, list[NcaaStatLine]] = {}
    report: list[dict[str, str]] = []
    name_counts = count_normalized_names(players)
    for player in players:
        player_id = player["player_id"]
        leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stats
            if row.get("player_id") == player_id
        }
        leagues.update(drafted_leagues.get(player_id, set()))
        key = normalize_person_key(player["name"])
        candidates = by_name.get(key, [])
        if not candidates:
            candidates = by_alias.get(person_alias_key(player["name"]), [])
        candidate_identity_count = len({line.source_id for line in candidates})
        disposition = match_disposition(
            eligible="NCAA" in leagues,
            name_count=name_counts.get(key, 0),
            has_candidates=bool(candidates),
            candidate_identity_count=candidate_identity_count,
            source_availability=source_availability,
        )
        if disposition == "matched":
            matched[player_id] = candidates
            report.extend(
                build_match_row(
                    player,
                    line,
                    disposition=disposition,
                    source_availability=source_availability,
                )
                for line in candidates
            )
        else:
            report.append(
                build_match_row(
                    player,
                    None,
                    disposition=disposition,
                    source_availability=source_availability,
                )
            )

    matched_scopes = {
        (player_id, line.season)
        for player_id, lines in matched.items()
        for line in lines
    }
    output_stats = [
        row
        for row in base_stats
        if not (
            row.get("timing") == "pre_draft"
            and normalize_league_name(row.get("league", "")) == "NCAA"
            and (row.get("player_id", ""), row.get("season", "")) in matched_scopes
        )
    ]
    output_advanced = [
        row
        for row in base_advanced
        if not (
            row.get("timing") == "pre_draft"
            and normalize_league_name(row.get("league", "")) == "NCAA"
            and (row.get("player_id", ""), row.get("season", "")) in matched_scopes
        )
    ]
    for player_id, lines in sorted(matched.items()):
        output_stats.extend(build_stat_line(player_id, line) for line in lines)
        output_advanced.extend(
            build_advanced_line(player_id, line) for line in lines if has_advanced_stats(line)
        )

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stats)
    write_table(
        target_root / "advanced_stat_lines.csv", ADVANCED_STAT_LINE_COLUMNS, output_advanced
    )
    write_table(target_root / "ncaa_stat_matches.csv", NCAA_MATCH_COLUMNS, report)
    return NcaaStatsEnrichmentSummary(
        len(players),
        len(source_lines),
        len(matched),
        len(output_stats),
        len(output_advanced),
        target_root / "ncaa_stat_matches.csv",
        source_availability,
        count_dispositions(report),
    )


def classify_available_sources(
    sources: list[NcaaStatSource],
) -> tuple[list[NcaaStatSource], str]:
    available = [
        source
        for source in sources
        if source.source_path is not None and source.source_path.is_file()
    ]
    if not available:
        return [], "unavailable"
    if len(available) < len(sources):
        return available, "partial"
    return available, "available"


def match_disposition(
    *,
    eligible: bool,
    name_count: int,
    has_candidates: bool,
    source_availability: str,
    candidate_identity_count: int = 1,
) -> str:
    if not eligible:
        return "not_eligible"
    if name_count != 1 or candidate_identity_count > 1:
        return "ambiguous_identity"
    if source_availability == "unavailable":
        return "source_unavailable"
    if not has_candidates:
        return "unmatched_in_cached_source"
    return "matched"


def count_dispositions(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        disposition = row["disposition"]
        counts[disposition] = counts.get(disposition, 0) + 1
    return counts


def load_ncaa_source_lines(sources: list[NcaaStatSource]) -> list[NcaaStatLine]:
    lines: list[NcaaStatLine] = []
    for source in sources:
        raw = source.source_path.read_text(encoding="utf-8") if source.source_path else ""
        if source.provider == "collegehockeyinc":
            lines.extend(parse_college_hockey_inc(raw, source))
        elif source.provider == "uscho":
            lines.extend(parse_uscho(raw, source))
        else:
            raise ValueError(f"unsupported NCAA provider: {source.provider}")
    return lines


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[tuple[str, str]] = []
        self.rows: list[list[tuple[str, str]]] = []
        self.current_href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and "data" in (attributes.get("class") or "").split():
            self.in_table = True
        elif self.in_table and tag in {"th", "td"}:
            self.in_cell = True
            self.current_cell = []
            self.current_href = ""
        elif self.in_cell and tag == "a":
            self.current_href = attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_table and tag in {"th", "td"} and self.in_cell:
            text = re.sub(r"\s+", " ", "".join(self.current_cell)).strip()
            self.current_row.append((text, self.current_href))
            self.in_cell = False
        elif self.in_table and tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
        elif self.in_table and tag == "table":
            self.in_table = False


def parse_college_hockey_inc(raw: str, source: NcaaStatSource) -> list[NcaaStatLine]:
    parser = TableParser()
    parser.feed(raw)
    if not parser.rows:
        raise ValueError("College Hockey Inc. payload has no statistics table")
    header_index = next(
        (
            index
            for index, row in enumerate(parser.rows)
            if {"Name", "GP"}.issubset({cell[0] for cell in row})
        ),
        -1,
    )
    if header_index < 0:
        raise ValueError("College Hockey Inc. payload has no player statistics header")
    headers = [cell[0] for cell in parser.rows[header_index]]
    return [
        line
        for row in parser.rows[header_index + 1 :]
        if (line := college_hockey_row(headers, row, source)) is not None
    ]


def college_hockey_row(
    headers: list[str],
    cells: list[tuple[str, str]],
    source: NcaaStatSource,
) -> NcaaStatLine | None:
    values = {
        header: cells[index][0] if index < len(cells) else ""
        for index, header in enumerate(headers)
    }
    name_index = headers.index("Name") if "Name" in headers else -1
    name = values.get("Name", "")
    if not name or name_index < 0:
        return None
    position = values.get("Pos.", values.get("Pos", "")).strip().casefold()
    if source.kind != "goalies" and position in {"g", "goalie"}:
        return None
    href = cells[name_index][1]
    source_id = href.rstrip("/").split("/")[-1] if href else normalize_person_key(name)
    player_url = (
        f"https://collegehockeyinc.com{href}" if href.startswith("/") else source.source_url
    )
    if source.kind == "goalies":
        return NcaaStatLine(
            name,
            source_id,
            player_url,
            source.provider,
            source.season,
            values.get("Team", ""),
            values.get("GP", ""),
            goalie_minutes=values.get("MIN", ""),
            saves=values.get("SV", ""),
            goals_against=values.get("GA", ""),
            save_percentage=values.get("SV%", ""),
            goals_against_average=values.get("GAA", ""),
            wins=values.get("W", ""),
            losses=values.get("L", ""),
            ties=values.get("T", ""),
            shutouts=values.get("SO", ""),
        )
    return NcaaStatLine(
        name,
        source_id,
        player_url,
        source.provider,
        source.season,
        values.get("Team", ""),
        values.get("GP", ""),
        values.get("G", ""),
        values.get("A", ""),
        values.get("PTS", ""),
        plus_minus=values.get("+/-", ""),
        shots=values.get("Shots", ""),
        blocks=values.get("Blk", ""),
        faceoff_wins=values.get("FW", ""),
        faceoff_losses=values.get("FL", ""),
        faceoff_percentage=values.get("FO%", ""),
    )


def parse_uscho(raw: str, source: NcaaStatSource) -> list[NcaaStatLine]:
    match = re.search(r'data-page="([^"]+)"', raw)
    if not match:
        raise ValueError("USCHO payload has no structured data-page")
    payload = json.loads(html.unescape(match.group(1)))
    content = payload.get("props", {}).get("content", {})
    data = content.get("data", {})
    lines = [uscho_skater(row, source) for row in data.get("scoring", {}).get("data", [])]
    lines.extend(uscho_goalie(row, source) for row in data.get("goaltending", {}).get("data", []))
    if not lines:
        raise ValueError("USCHO payload has no national player statistics")
    return lines


def uscho_skater(row: dict[str, object], source: NcaaStatSource) -> NcaaStatLine:
    source_id = str(row.get("player_id", ""))
    return NcaaStatLine(
        name=f"{row.get('first', '')} {row.get('last', '')}".strip(),
        source_id=source_id,
        source_url=f"https://www.uscho.com/stats/player/mid,{source_id}/",
        provider=source.provider,
        season=source.season,
        team=str(row.get("shortname", "")),
        games=str(row.get("gp", "")),
        goals=str(row.get("g", "")),
        assists=str(row.get("a", "")),
        points=str(row.get("pts", "")),
        plus_minus=str(row.get("plsmns", "")),
        shots=str(row.get("shots", "")),
        blocks=str(row.get("bl", "")),
        faceoff_percentage=str(row.get("fop", "")),
    )


def uscho_goalie(row: dict[str, object], source: NcaaStatSource) -> NcaaStatLine:
    source_id = str(row.get("player_id", ""))
    return NcaaStatLine(
        name=f"{row.get('first', '')} {row.get('last', '')}".strip(),
        source_id=source_id,
        source_url=f"https://www.uscho.com/stats/player/mid,{source_id}/",
        provider=source.provider,
        season=source.season,
        team=str(row.get("shortname", "")),
        games=str(row.get("gp", "")),
        goalie_minutes=clean_markup(str(row.get("min", ""))),
        saves=str(row.get("saves", "")),
        goals_against=str(row.get("ga", "")),
        save_percentage=str(row.get("svp", "")),
        goals_against_average=clean_markup(str(row.get("gaa", ""))),
        wins=str(row.get("w", "")),
        losses=str(row.get("l", "")),
        ties=str(row.get("t", "")),
        shutouts=str(row.get("sho", "")),
    )


def clean_markup(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def build_stat_line(player_id: str, line: NcaaStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": "NCAA",
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true",
        "source": line.provider,
        "source_id": line.source_id,
        "source_url": line.source_url,
        "goalie_minutes": line.goalie_minutes,
        "shots_against": "",
        "saves": line.saves,
        "goals_against": line.goals_against,
        "save_percentage": line.save_percentage,
        "goals_against_average": line.goals_against_average,
        "wins": line.wins,
        "losses": line.losses,
        "ties": line.ties,
        "shutouts": line.shutouts,
    }


def build_advanced_line(player_id: str, line: NcaaStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": "NCAA",
        "team": line.team,
        "timing": "pre_draft",
        "regular_season": "true",
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


def has_advanced_stats(line: NcaaStatLine) -> bool:
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
    player: dict[str, str],
    line: NcaaStatLine | None,
    *,
    disposition: str,
    source_availability: str,
) -> dict[str, str]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": "true" if disposition == "matched" else "false",
        "disposition": disposition,
        "source_availability": source_availability,
        "provider": line.provider if line else "",
        "source_name": line.name if line else "",
        "source_id": line.source_id if line else "",
        "source_url": line.source_url if line else "",
        "team": line.team if line else "",
        "games": line.games if line else "",
        "points": line.points if line else "",
        "save_percentage": line.save_percentage if line else "",
    }
