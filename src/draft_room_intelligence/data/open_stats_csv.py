"""Overlay flexible open-source stat CSVs onto normalized season stat lines."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.chl_stats import (
    count_normalized_names,
    normalize_person_key,
    read_drafted_league_hints,
    read_table,
)
from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    first_text,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name
from draft_room_intelligence.data.stat_reconciliation import (
    RECONCILIATION_AUDIT_COLUMNS,
    reconcile_stat_lines,
)

OPEN_STATS_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "source_name",
    "source",
    "source_id",
    "source_url",
    "league",
    "team",
    "games",
    "goals",
    "assists",
    "points",
    "regular_season",
]


@dataclass(frozen=True)
class OpenStatsCsvSource:
    path: Path
    source: str
    season: str
    league: str = ""
    regular_season: bool = True
    timing: str = "pre_draft"


@dataclass(frozen=True)
class OpenStatsLine:
    name: str
    nationality: str
    source: str
    source_id: str
    source_url: str
    season: str
    league: str
    team: str
    games: str
    goals: str
    assists: str
    points: str
    regular_season: bool
    timing: str
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
class OpenStatsCsvEnrichmentSummary:
    players_scanned: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    match_report_path: Path


def enrich_open_stats_csv(
    base_dir: str | Path,
    output_dir: str | Path,
    sources: list[OpenStatsCsvSource],
    *,
    allow_new_leagues: bool = False,
) -> OpenStatsCsvEnrichmentSummary:
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
    source_lines = load_open_stats_lines(sources)
    source_by_name_league: dict[tuple[str, str], list[OpenStatsLine]] = {}
    for line in source_lines:
        key = (normalize_person_key(line.name), normalize_league_name(line.league))
        source_by_name_league.setdefault(key, []).append(line)

    matched_by_player_id: dict[str, list[OpenStatsLine]] = {}
    report_rows: list[dict[str, str]] = []
    player_name_counts = count_normalized_names(players)
    for player in players:
        player_leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stat_lines
            if row.get("player_id") == player["player_id"]
        }
        player_leagues.update(drafted_leagues.get(player["player_id"], set()))
        candidates: list[OpenStatsLine] = []
        player_key = normalize_person_key(player["name"])
        for league in player_leagues:
            candidates.extend(source_by_name_league.get((player_key, league), []))
        if allow_new_leagues and player_name_counts.get(player_key) == 1:
            for (source_name_key, _), source_candidates in source_by_name_league.items():
                if source_name_key == player_key:
                    candidates.extend(source_candidates)
        candidates = (
            deduplicate_open_stats_lines(candidates)
            if player_name_counts.get(player_key) == 1
            else []
        )
        if candidates:
            matched_by_player_id[player["player_id"]] = candidates
            nationalities = {line.nationality for line in candidates if line.nationality}
            if not player.get("nationality") and len(nationalities) == 1:
                player["nationality"] = nationalities.pop()
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
            and normalize_league_name(row.get("league", ""))
            in matched_leagues_by_player[row["player_id"]]
            and row.get("source") in {"hockeydb", "wikipedia", "open-stats"}
        )
    ]
    for player_id, lines in sorted(matched_by_player_id.items()):
        output_stat_lines.extend(build_normalized_stat_line(player_id, line) for line in lines)

    reconciliation = reconcile_stat_lines(output_stat_lines)
    output_stat_lines = reconciliation.rows
    audit_path = target_root / "stat_line_reconciliation_audit.csv"
    existing_audit_rows = read_table(audit_path) if audit_path.exists() else []
    audit_rows = deduplicate_audit_rows(existing_audit_rows + reconciliation.audit_rows)

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(target_root / "open_stats_matches.csv", OPEN_STATS_MATCH_COLUMNS, report_rows)
    write_table(audit_path, RECONCILIATION_AUDIT_COLUMNS, audit_rows)

    return OpenStatsCsvEnrichmentSummary(
        players_scanned=len(players),
        source_rows=len(source_lines),
        matched_players=len(matched_by_player_id),
        output_stat_lines=len(output_stat_lines),
        match_report_path=target_root / "open_stats_matches.csv",
    )


def deduplicate_audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    output: list[dict[str, str]] = []
    for row in rows:
        key = tuple(row.get(column, "") for column in RECONCILIATION_AUDIT_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def load_open_stats_lines(sources: list[OpenStatsCsvSource]) -> list[OpenStatsLine]:
    lines: list[OpenStatsLine] = []
    for source in sources:
        for row in read_table(source.path):
            name = first_text(row, "name", "player", "Player", "Name")
            if not name:
                continue
            league = normalize_league_name(first_text(row, "league", "League") or source.league)
            if not league:
                continue
            lines.append(
                OpenStatsLine(
                    name=name,
                    nationality=first_text(row, "nationality", "Nation", "Country"),
                    source=first_text(row, "source", "Source") or source.source,
                    source_id=first_text(row, "source_id", "player_id", "id", "ID")
                    or normalize_person_key(name),
                    source_url=first_text(row, "source_url", "url", "URL"),
                    season=first_text(row, "season", "Season") or source.season,
                    league=league,
                    team=first_text(row, "team", "Team"),
                    games=first_text(row, "games", "GP", "Games"),
                    goals=first_text(row, "goals", "G", "Goals"),
                    assists=first_text(row, "assists", "A", "Assists"),
                    points=first_text(row, "points", "PTS", "TP", "Points"),
                    regular_season=parse_regular_season(
                        first_text(row, "regular_season", "season_type", "Stage"),
                        source.regular_season,
                    ),
                    timing=first_text(row, "timing", "Timing") or source.timing,
                    goalie_minutes=first_text(row, "goalie_minutes", "minutes", "MIN", "Mins"),
                    shots_against=first_text(row, "shots_against", "SA", "Shots Against"),
                    saves=first_text(row, "saves", "SV", "Saves"),
                    goals_against=first_text(row, "goals_against", "GA", "Goals Against"),
                    save_percentage=normalize_save_percentage(
                        first_text(row, "save_percentage", "SV%", "Save Percentage")
                    ),
                    goals_against_average=first_text(row, "goals_against_average", "GAA"),
                    wins=first_text(row, "wins", "W"),
                    losses=first_text(row, "losses", "L"),
                    ties=first_text(row, "ties", "T", "OTL"),
                    shutouts=first_text(row, "shutouts", "SO", "Shutouts"),
                )
            )
    return lines


def parse_regular_season(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"regular", "regular season", "true", "1", "yes"}:
        return True
    if normalized in {"playoffs", "playoff", "postseason", "false", "0", "no"}:
        return False
    return default


def normalize_save_percentage(value: str) -> str:
    if not value:
        return ""
    try:
        number = float(value)
    except ValueError:
        return value
    if number > 1.0:
        number = number / 100
    return f"{number:.3f}"


def deduplicate_open_stats_lines(lines: list[OpenStatsLine]) -> list[OpenStatsLine]:
    seen: set[tuple[str, str, str, bool, str]] = set()
    deduped: list[OpenStatsLine] = []
    for line in lines:
        key = (
            line.season,
            normalize_league_name(line.league),
            normalize_person_key(line.team),
            line.regular_season,
            line.source,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def build_normalized_stat_line(player_id: str, line: OpenStatsLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": normalize_league_name(line.league),
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": "",
        "timing": line.timing,
        "regular_season": "true" if line.regular_season else "false",
        "source": "open-stats",
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
    line: OpenStatsLine | None,
    *,
    matched: bool,
) -> dict[str, str]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": "true" if matched else "false",
        "source_name": line.name if line else "",
        "source": line.source if line else "",
        "source_id": line.source_id if line else "",
        "source_url": line.source_url if line else "",
        "league": line.league if line else "",
        "team": line.team if line else "",
        "games": line.games if line else "",
        "goals": line.goals if line else "",
        "assists": line.assists if line else "",
        "points": line.points if line else "",
        "regular_season": "true" if line and line.regular_season else "false" if line else "",
    }
