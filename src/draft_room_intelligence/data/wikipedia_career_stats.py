"""Overlay Wikipedia career-stat tables onto normalized demo stat lines."""

from __future__ import annotations

import csv
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from draft_room_intelligence.data.chl_stats import normalize_person_key, read_table
from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name
from draft_room_intelligence.data.wikipedia_bio import query_wikipedia


WIKIPEDIA_CAREER_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "title",
    "league",
    "team",
    "games",
    "goals",
    "assists",
    "points",
    "regular_season",
    "source_url",
]


@dataclass(frozen=True)
class WikipediaCareerStatLine:
    player_id: str
    name: str
    title: str
    source_url: str
    season: str
    league: str
    team: str
    games: str
    goals: str
    assists: str
    points: str
    regular_season: bool


@dataclass(frozen=True)
class WikipediaCareerStatsSummary:
    players_scanned: int
    pages_fetched: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    match_report_path: Path


def enrich_wikipedia_career_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    *,
    season: str,
    cache_dir: str | Path | None = None,
    request_delay_seconds: float = 0.2,
) -> WikipediaCareerStatsSummary:
    source_root = Path(base_dir)
    target_root = Path(output_dir)
    if not source_root.exists():
        raise ValueError(f"missing base dataset directory: {source_root}")

    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    players = read_table(source_root / "players.csv")
    players_by_id = {player["player_id"]: player for player in players}
    base_stat_lines = read_table(source_root / "season_stat_lines.csv")
    wiki_matches = read_table(source_root / "wikipedia_bio_matches.csv")
    matched_pages = [row for row in wiki_matches if row.get("matched") == "true" and row.get("title")]

    source_lines: list[WikipediaCareerStatLine] = []
    fetched_pages = 0
    for index, row in enumerate(matched_pages):
        if index and request_delay_seconds > 0:
            time.sleep(request_delay_seconds)
        try:
            wikitext = fetch_cached_wikitext(row["title"], cache_dir=cache_dir)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            wikitext = ""
        if wikitext:
            fetched_pages += 1
        player = players_by_id.get(row["player_id"], {})
        if player.get("position") == "G":
            continue
        source_lines.extend(parse_career_stat_lines(wikitext, row, season=season))

    source_by_player: dict[str, list[WikipediaCareerStatLine]] = {}
    for line in source_lines:
        source_by_player.setdefault(line.player_id, []).append(line)

    matched_keys: set[tuple[str, str, str, bool]] = set()
    report_rows: list[dict[str, str]] = []
    output_stat_lines: list[dict[str, str]] = []
    for row in base_stat_lines:
        player_id = row.get("player_id", "")
        existing_key = stat_row_source_key(row)
        if existing_key is not None:
            matched_keys.add(existing_key)
        if row.get("timing") != "pre_draft" or row.get("source") != "wikipedia":
            output_stat_lines.append(row)
            continue
        candidates = [
            line
            for line in source_by_player.get(player_id, [])
            if line.season == row.get("season")
            and normalize_league_name(line.league) == normalize_league_name(row.get("league", ""))
        ]
        if not candidates:
            output_stat_lines.append(row)
            continue
        for candidate in candidates:
            matched_keys.add(source_line_key(candidate))
            output_stat_lines.append(build_normalized_stat_line(row, candidate))

    for player_lines in source_by_player.values():
        for line in player_lines:
            key = source_line_key(line)
            if key in matched_keys:
                continue
            matched_keys.add(key)
            output_stat_lines.append(build_normalized_stat_line({}, line))

    for line in source_lines:
        key = source_line_key(line)
        matched = key in matched_keys
        report_rows.append(build_match_row(players_by_id.get(line.player_id, {}), line, matched=matched))

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(
        target_root / "wikipedia_career_stat_matches.csv",
        WIKIPEDIA_CAREER_MATCH_COLUMNS,
        report_rows,
    )

    return WikipediaCareerStatsSummary(
        players_scanned=len(matched_pages),
        pages_fetched=fetched_pages,
        source_rows=len(source_lines),
        matched_players=len({row[0] for row in matched_keys}),
        output_stat_lines=len(output_stat_lines),
        match_report_path=target_root / "wikipedia_career_stat_matches.csv",
    )


def parse_career_stat_lines(
    wikitext: str,
    match_row: dict[str, str],
    *,
    season: str,
) -> list[WikipediaCareerStatLine]:
    table = extract_first_career_table(wikitext)
    if not table:
        return []
    lines: list[WikipediaCareerStatLine] = []
    for cells in parse_wikitable_rows(table):
        if len(cells) < 13 or not season_matches(cells[0], season) or is_total_row(cells):
            continue
        common = {
            "player_id": match_row["player_id"],
            "name": match_row["name"],
            "title": match_row["title"],
            "source_url": match_row.get("source_url", ""),
            "season": normalize_season(cells[0]),
            "team": cells[1],
            "league": cells[2],
        }
        regular = cells[3:8]
        playoffs = cells[8:13]
        if is_skater_stat_group(regular):
            lines.append(
                WikipediaCareerStatLine(
                    **common,
                    games=regular[0],
                    goals=regular[1],
                    assists=regular[2],
                    points=regular[3],
                    regular_season=True,
                )
            )
        if is_skater_stat_group(playoffs):
            lines.append(
                WikipediaCareerStatLine(
                    **common,
                    games=playoffs[0],
                    goals=playoffs[1],
                    assists=playoffs[2],
                    points=playoffs[3],
                    regular_season=False,
                )
            )
    return lines


def extract_first_career_table(wikitext: str) -> str:
    career_index = wikitext.lower().find("career statistics")
    if career_index == -1:
        return ""
    table_start = wikitext.find("{|", career_index)
    if table_start == -1:
        return ""
    international_index = wikitext.lower().find("international", career_index)
    table_end = wikitext.find("|}", table_start)
    if table_end == -1:
        return ""
    if international_index != -1 and international_index < table_start:
        return ""
    return wikitext[table_start : table_end + 2]


def parse_wikitable_rows(table: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_row in re.split(r"\n\|-", table):
        cells = parse_wikitable_cells(raw_row)
        if cells:
            rows.append(cells)
    return rows


def parse_wikitable_cells(raw_row: str) -> list[str]:
    cells: list[str] = []
    for line in raw_row.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("{|") or stripped.startswith("|}") or stripped.startswith("!"):
            continue
        if not stripped.startswith("|"):
            continue
        stripped = stripped.lstrip("|").strip()
        if stripped.startswith("-") or stripped.startswith("bgcolor") or stripped.startswith("rowspan"):
            continue
        cells.extend(clean_wiki_cell(part) for part in stripped.split("||"))
    return [cell for cell in cells if cell != ""]


def clean_wiki_cell(value: str) -> str:
    text = re.sub(r"<ref[^>/]*/>", "", value)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def season_matches(value: str, season: str) -> bool:
    return normalize_season(value) == season


def normalize_season(value: str) -> str:
    text = clean_wiki_cell(value).replace("–", "-").replace("—", "-")
    match = re.search(r"(\d{4})-(\d{2})", text)
    return match.group(0) if match else text


def is_total_row(cells: list[str]) -> bool:
    return any("total" in cell.lower() for cell in cells[:3])


def is_nonzero_games(value: str) -> bool:
    normalized = clean_wiki_cell(value).replace("–", "-").replace("—", "-")
    return normalized.isdigit() and int(normalized) > 0


def is_skater_stat_group(values: list[str]) -> bool:
    if len(values) < 4 or not is_nonzero_games(values[0]):
        return False
    return all(clean_wiki_cell(value).isdigit() for value in values[1:4])


def source_line_key(line: WikipediaCareerStatLine) -> tuple[str, str, str, bool]:
    return (
        line.player_id,
        line.season,
        normalize_league_name(line.league),
        line.regular_season,
    )


def stat_row_source_key(row: dict[str, str]) -> tuple[str, str, str, bool] | None:
    if row.get("timing") != "pre_draft" or row.get("source") != "wikipedia-career":
        return None
    return (
        row.get("player_id", ""),
        row.get("season", ""),
        normalize_league_name(row.get("league", "")),
        row.get("regular_season", "true").lower() != "false",
    )


def build_normalized_stat_line(
    placeholder: dict[str, str],
    line: WikipediaCareerStatLine,
) -> dict[str, str]:
    return {
        "player_id": line.player_id,
        "season": line.season,
        "league": placeholder.get("league") or normalize_league_name(line.league),
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": placeholder.get("age", ""),
        "timing": "pre_draft",
        "regular_season": "true" if line.regular_season else "false",
        "source": "wikipedia-career",
        "source_id": line.title,
        "source_url": line.source_url,
    }


def build_match_row(
    player: dict[str, str],
    line: WikipediaCareerStatLine,
    *,
    matched: bool,
) -> dict[str, str]:
    return {
        "player_id": line.player_id,
        "name": player.get("name", line.name),
        "matched": "true" if matched else "false",
        "title": line.title,
        "league": line.league,
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "regular_season": "true" if line.regular_season else "false",
        "source_url": line.source_url,
    }


def fetch_cached_wikitext(title: str, *, cache_dir: str | Path | None) -> str:
    cache_root = Path(cache_dir) if cache_dir is not None else None
    cache_path = cache_root / f"{normalize_person_key(title)}.json" if cache_root else None
    if cache_path and cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return str(data.get("wikitext", ""))

    parsed = query_wikipedia(
        {
            "action": "parse",
            "format": "json",
            "page": title,
            "prop": "wikitext",
        }
    )
    wikitext = str(parsed.get("parse", {}).get("wikitext", {}).get("*", ""))
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "title": title,
                    "source_url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                    "wikitext": wikitext,
                },
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    return wikitext
